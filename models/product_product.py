from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import config
import logging

import requests
import json
import urllib.request
import urllib.parse
from .sign_api_request import cal_sign, get_timestamp, get_cipher_shop_key

_logger = logging.getLogger(__name__)

class TikTokProduct(models.Model):
    _name = 'tiktok.product'
    _description = 'TikTok Product'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'product_name_tiktok'

    product_name_tiktok = fields.Char('Name', tracking=True, readonly=True)
    product_price_tiktok = fields.Float('Price', tracking=True, compute='_compute_product_product_base', store=True)
    product_quantity_tiktok = fields.Integer('Quantity', tracking=True, compute='_compute_product_product_base', store=True)
    product_sku_tiktok = fields.Char('SKU ID', tracking=True, readonly=True)
    product_tiktok_id = fields.Char('TikTok ID', tracking=True, readonly=True)
    warehouse_tiktok_id = fields.Char('Warehouse ID', tracking=True, readonly=True)
    tiktok_currency = fields.Char(string="Currency" ,tracking=True, readonly=True)
    product_id = fields.Many2one('product.product', 'Product', tracking=True)
    is_mapping = fields.Boolean('Is Mapping', default=False)
    
    
    @api.constrains('product_id')
    def _check_product_id(self):
        for record in self:
            if record.product_id:
                product = self.env['tiktok.product'].search([
                    ('product_id', '=', record.product_id.id), 
                    ('id', '!=', record.id)], limit=1)
                if product:
                    raise UserError('Product already mapped to another TikTok product')
    
    @api.depends('product_id', 'product_id.free_qty')
    def _compute_product_product_base(self):
        price =  self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.pricelist_id')
        warehouse_id = self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.warehouse_id')
        if price:
            price = self.env['product.pricelist'].browse(int(price))
            for record in self:
                price_approved = self.env['product.pricelist.item'].search([
                            ('product_tmpl_id', '=', record.product_id.product_tmpl_id.id),
                            ('pricelist_id', '=', price.id),
                            ('effect_type', '=', 'approve'),
                            ('price_state', '=', 'in_use')
                        ], limit=1).price_approved
                record.product_quantity_tiktok = record.product_id.with_context(
                warehouse=self.env['stock.warehouse'].browse(int(warehouse_id)).id).free_qty
                record.product_price_tiktok = price_approved
        else:
            for record in self:
                record.product_quantity_tiktok =  record.product_id.with_context(
                warehouse=self.env['stock.warehouse'].browse(int(warehouse_id)).id).free_qty
                record.product_price_tiktok = record.product_id.list_price    
    
    def _check_status_mapping(self):
        for rec in self:
            if rec.product_id:
                rec.product_id.write({'is_mapping': True})
            if rec._origin.product_id:
                rec._origin.product_id.write({'is_mapping': False})

    def write(self, vals):
        res = super(TikTokProduct, self).write(vals)
        if vals.get('product_id'):
            self.is_mapping = True
            self._check_status_mapping()
        return res
            
    def unlink(self):
        for rec in self:
            if rec.product_id:
                rec.product_id.write({'is_mapping': False})
        return super(TikTokProduct, self).unlink()
     
    def get_product_list_data(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.url_tiktok', '')
        token = self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.token_tiktok', '')
        app_key = config.get('app_key_tiktok', False)
        app_secret = config.get('app_secret_tiktok', False)
        
        path = "/product/202309/products/search"
        url = f"{base_url}{path}"
        headers = {
             "Content-Type": "application/json",
             "x-tts-access-token": f"{token}",
        }
        shop_cipher = get_cipher_shop_key(app_key, app_secret, token, base_url)
        params = {
            # "access_token": token,
            "app_key": app_key,
            "page_size": 100,
            "shop_cipher": shop_cipher.get("data").get("shops")[0].get("cipher"),
            "timestamp": get_timestamp(),
            "version": "202309",
        }

        params_signed = urllib.parse.urlencode(params)
        url_signed = f"{url}?{params_signed}"
        params['sign'] = cal_sign(url_signed, app_secret)
        
        response = requests.post(url, headers=headers, params=params, verify=False, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    
    def save_product_list_data(self):
        try:
            datas = self.get_product_list_data().get('data', {}).get('products', [])
            if not datas:
                pass
            else:
                product_vals = []
                for product in datas:
                    product_id = self.env['tiktok.product'].sudo().search([
                        ('product_tiktok_id', '=', product.get('id', ''))], limit=1)
                    sku = product.get("skus", [{}])[0]
                    if not product_id:
                        product_vals.append({
                            'product_name_tiktok': product.get("title", ""),
                            'product_tiktok_id': product.get("id", ""),
                            'product_price_tiktok': sku.get("price", {}).get("tax_exclusive_price", ""),
                            'product_quantity_tiktok': sku.get("inventory", [{}])[0].get("quantity", ""),
                            'product_sku_tiktok': sku.get('id', ''),
                            'tiktok_currency': sku.get("price", {}).get("currency", ""),
                            'warehouse_tiktok_id': sku.get("inventory", [{}])[0].get("warehouse_id", ''),
                        })
                    else:
                        product_id.write({
                            'product_sku_tiktok': sku.get('id', ''),
                            'warehouse_tiktok_id': sku.get("inventory", [{}])[0].get("warehouse_id", '')
                        })
                if product_vals:
                    self.env['tiktok.product'].sudo().create(product_vals)
        except Exception as e:
            if self._context.get('bypass_error', False):
                pass
            else:
                raise UserError(e)
        return {
            'name': _("Products"),
            'type': 'ir.actions.act_window',
            'res_model': 'tiktok.product',
            'view_mode': 'tree',
            'views': [(False, 'tree')],
        }

            

class Product(models.Model):
    _inherit = 'product.product'

    is_mapping = fields.Boolean('Is Mapping', default=False)

class SyncTikTokProduct(models.Model):
    _name = 'sync.tiktok.product'
    _description = 'Sync TikTok Product'

    name = fields.Char('Name', compute='_compute_name', store=True)
    date = fields.Datetime('Date', default=fields.Datetime.now)
    prices_list_id = fields.Many2one('product.pricelist', 'Pricelist', required=True)
    is_sync = fields.Boolean('Is Sync', default=False)
    
    
    @api.depends('date')
    def _compute_name(self):
        for record in self:
            record.name = f"Sync TikTok Product - {record.date}"
    
    def get_tiktok_product_data(self):
        products = self.env['tiktok.product'].search([])
        if not products:
            return []
        else:
            product_vals = []
            for product in products:
                if product.product_id.product_tmpl_id.use_approved_prices:
                    price_unit = self.env['product.pricelist.item'].search([
                        ('product_tmpl_id', '=', product.product_id.product_tmpl_id.id),
                        ('pricelist_id', '=', self.prices_list_id.id),
                        ('effect_type', '=', 'approve'),
                        ('price_state', '=', 'in_use')
                    ], limit=1).price_approved
                product_vals.append({
                    'tiktok_product_id': product.id,
                    'price_to_sync': price_unit,
                    'quantity_to_sync': product.product_id.free_qty
                })
            return product_vals
        
    def _get_header_tiktok(self, token):
        return {
            "Content-Type": "application/json",
            "x-tts-access-token": f"{token}",
        }

    def sync_quantity(self):
    #Path: /product/202309/products/{product_id}/inventory/update Method: [POST]
        base_url = self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.url_tiktok', '')
        token = self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.token_tiktok', '')
        app_key = config.get('app_key_tiktok', False)
        app_secret = config.get('app_secret_tiktok', False)
        for data in self.get_tiktok_product_data():
            record = self.env['tiktok.product'].browse(data.get('tiktok_product_id'))
            url = f"{base_url}/product/202309/products/{record.product_tiktok_id}/inventory/update"
            
            headers = self._get_header_tiktok(token)
            body_inven = {
                "skus": [
                    {
                    "id": f"{record.product_sku_tiktok}",
                    "inventory": [
                        {
                        "quantity": record.product_quantity_tiktok,
                        "warehouse_id": f"{record.warehouse_tiktok_id}",
                        }
                    ]
                    }
                ]
            }
            shop_cipher = get_cipher_shop_key(app_key, app_secret, token, base_url)
            params = {
                "access_token": token,
                "app_key": app_key,
                "shop_cipher": shop_cipher.get("data").get("shops")[0].get("cipher"),
                "timestamp": get_timestamp(),
                "version": "202309",
            }
            params_signed = urllib.parse.urlencode(params)
            url_signed = f"{url}?{params_signed}"
            params['sign'] = cal_sign(url_signed, app_secret, body_inven)
            response = requests.post(url, headers=headers, params=params, verify=False, timeout=30, json=body_inven)
            if response.status_code == 200:
                self.is_sync = True 
                _logger.info('Sync Price Success')
            else:
                pass
    
    def sync_price(self):
        #Path: /product/202309/products/{product_id}/prices/update Method: [POST]
        base_url = self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.url_tiktok', '')
        token = self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.token_tiktok', '')
        app_key = config.get('app_key_tiktok', False)
        app_secret = config.get('app_secret_tiktok', False)
        for data in self.get_tiktok_product_data():
            record = self.env['tiktok.product'].browse(data.get('tiktok_product_id'))
            url = f"{base_url}/product/202309/products/{record.product_tiktok_id}/prices/update"
            
            headers = self._get_header_tiktok(token)
            body_price = {
                "skus": [
                    {
                    "id": f"{record.product_sku_tiktok}",
                    "price": {
                        "amount": str(round(data['price_to_sync'])),
                        "currency": f"{record.tiktok_currency}",
                    },
                },],
            }
            shop_cipher = get_cipher_shop_key(app_key, app_secret, token, base_url)
            params = {
                "access_token": token,
                "app_key": app_key,
                "shop_cipher": shop_cipher.get("data").get("shops")[0].get("cipher"),
                "timestamp": get_timestamp(),
                "version": "202309",
            }
            params_signed = urllib.parse.urlencode(params)
            url_signed = f"{url}?{params_signed}"
            params['sign'] = cal_sign(url_signed, app_secret, body_price)
            response = requests.post(url, headers=headers, params=params, verify=False, timeout=30, json=body_price)
            if response.status_code == 200:
                self.is_sync = True 
                _logger.info('Sync Price Success')
            else:
                pass
            
            
    def sync_product(self):
        try:
            if self.get_tiktok_product_data():
                data = {
                    'prices_list_id': self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.pricelist_id'),
                }
                rec = self.create(data)
                rec.sync_price()
                rec.sync_quantity()
                
        except Exception as e:
            if self._context.get('bypass_error', False):
                pass
            else:
                raise UserError(e)
        