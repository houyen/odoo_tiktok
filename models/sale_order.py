from odoo import fields, models, _
from odoo.tools import config
from odoo.exceptions import UserError

import requests
import urllib.request
import urllib.parse
from datetime import datetime
from collections import Counter

from .sign_api_request import cal_sign, get_timestamp, get_cipher_shop_key


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    tictok_order_id = fields.Char('TikTok Order ID', readonly=True)
    tiktok_status = fields.Char('status', readonly=True)
    ecommerce_level = fields.Selection([
        ('tiktok', 'TikTok'),
        ('shopee', 'Shopee'),
        ('lazada', 'Lazada'),
        ('tiki', 'Tiki'),
        ('other', 'Other'),
    ], string='Ecommerce Level', default='other')
        
    def get_sale_order_list_data(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.url_tiktok', '')
        token = self.env['ir.config_parameter'].sudo().get_param('erp_tiktok.token_tiktok', '')
        app_key = config.get('app_key_tiktok', False)
        app_secret = config.get('app_secret_tiktok', False)
        
        path = "/order/202309/orders/search"
        url = f"{base_url}{path}"
        headers = {
             "Content-Type": "application/json",
             "x-tts-access-token": f"{token}",
        }
        shop_cipher = get_cipher_shop_key(app_key, app_secret, token, base_url)
        params = {
        "app_key": app_key, 
        "page_size": 100,
        "shop_cipher": shop_cipher.get("data").get("shops")[0].get("cipher"),
        "timestamp": get_timestamp(),
        "version": "202309",
        }
        #"order_status": 100, # UNPAID = 100; - ON_HOLD = 105; - AWAITING_SHIPMENT = 111; - AWAITING_COLLECTION = 112;
        # - PARTIALLY_SHIPPING = 114; - IN_TRANSIT = 121; - DELIVERED = 122; - COMPLETED = 130; - CANCELLED = 140;
        
        params_signed = urllib.parse.urlencode(params)
        url_signed = f"{url}?{params_signed}"
        params['sign'] = cal_sign(url_signed, app_secret)
        
        response = requests.post(url, headers=headers, params=params, verify=False, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return None

    def check_partner_id(self, email, name, phone_number, street):
        partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': name,
                'email': email,
                'mobile': phone_number,
                'type': 'contact', 
                'street': street,
            })
        return partner.id
                    
    def create_sale_order_from_api(self):
        try:
            datas = self.get_sale_order_list_data().get('data', {}).get('orders', [])
            if not datas:
                pass
            else:
                for order in datas:
                    order_id = self.env['sale.order'].sudo().search([
                        ('tictok_order_id', '=', order.get('id', ''))], limit=1)
                    transporter_id = self.env['res.partner'].sudo().search([('transporter_code', '=', 'TIK')], limit=1)
                    shipping_method_id = self.env['delivery.carrier'].sudo().search([('transporter_id', '=',transporter_id.id)], limit=1)
                    status = order.get('status', '')
                    if not order_id:
                        line_items = order.get("line_items", [])
                        product_counter = Counter([x.get('product_id') for x in line_items])
                        for line in line_items:
                            line["count_product"] = product_counter[line["product_id"]]
                        
                        def filter_line_items(line_items):
                            product_ids = {}
                            for item in line_items:
                                product_id = item['product_id']
                                if product_id not in product_ids:
                                    product_ids[product_id] = item
                            return list(product_ids.values())
                            
                        prepared_line_items = []
                        for line in filter_line_items(line_items):
                            tiktok_product_id = self.env['tiktok.product'].sudo().search([
                                ('product_tiktok_id', '=', line.get('product_id', ''))], limit=1)
                            if not tiktok_product_id:
                                tiktok_product_id = self.env['tiktok.product'].sudo().create({
                                    'product_name_tiktok': line.get('product_name', ''),
                                    'product_tiktok_id': line.get('product_id', ''),
                                    'product_price_tiktok': line.get('sale_price', ''),
                                    'product_sku_tiktok': line.get('sku_id', ''),
                                })
                                continue
                            else:
                                if tiktok_product_id.is_mapping:
                                    product = tiktok_product_id.product_id   
                                else:
                                    continue
                            prepared_line_items.append({
                                'product_id': product.id,
                                'product_uom_qty': line.get('count_product', 1),
                                'price_unit': line.get('sale_price', ''),
                            })
                        
                        data={
                            'name': order.get('id', ''),
                            'tictok_order_id': order.get('id', ''),
                            'partner_id': self.check_partner_id(order.get('buyer_email', ''), order.get('recipient_address',[]).get('name', ''), \
                                order.get('recipient_address',[]).get('phone_number', '') ,order.get('recipient_address',[]).get('address_detail', '')),
                            'note': order.get('buyer_message', ''),
                            'order_line': [(0, 0, line) for line in prepared_line_items],
                            'ecommerce_level': 'tiktok',
                            'tiktok_status': status,
                            'transporter_id': transporter_id.id,
                            'shipping_method_id': shipping_method_id.id if shipping_method_id else False,
                            'transport_order_ids': [(0, 0, {
                                'name': order.get('id', ''),
                                'transporter_id': transporter_id.id,
                                'cod': order.get('payment', {}).get('total_amount') if order.get('is_cod') != 'false' else 0,
                                'shipping_method_id': shipping_method_id.id if shipping_method_id else False,
                                'shipping_fee': order.get('payment', {}).get('shipping_fee'),
                                'pay_fee_type': 'customer',
                                'plan_picking_date': datetime.fromtimestamp(int(order.get('delivery_time'))) if order.get('delivery_time') else datetime.now(),
                                'plan_shipping_date': datetime.fromtimestamp(int(order.get('delivery_time'))) if order.get('delivery_time') else datetime.now(),
                            })],
                            'account_payment_ids': [(0, 0, {
                                'date': datetime.now(),
                                'name': 'TikTok -%s' % order.get('id', ''),
                                'amount_company_currency_signed': order.get('payment', {}).get('total_amount'),
                                'currency_id': self.env['res.currency'].sudo().search([('name', '=', 'VND')], limit=1).id,
                                'payment_method_line_id': self.env['account.payment.method.line'].sudo().search([('code', '=', 'manual')], limit=1).id,
                                'journal_id': self.env['account.journal'].sudo().search([('type', '=', 'bank')], limit=1).id,
                                'ref': order.get('id', ''),
                                'state': 'draft',
                            })],
                        }
                        if status == 'AWAITING_SHIPMENT':
                            order = self.env['sale.order'].sudo().create(data)
                            for payment in order.account_payment_ids:
                                payment.action_post()
 
                        elif status == 'CANCELLED':
                            data['state'] = 'cancel'
                            order = self.env['sale.order'].sudo().create(data)
                            for payment in order.account_payment_ids:
                                payment.action_post()
                        elif status not in ['AWAITING_SHIPMENT', 'CANCELLED']:
                            order = self.env['sale.order'].sudo().create(data)
                            order.action_confirm()
                            order.action_confirm()
                            for payment in order.account_payment_ids:
                                payment.action_post()
                        
                    else:
                        order_id.write({
                            'tiktok_status': status,
                            'shipping_method_id': shipping_method_id.id if shipping_method_id else False,
                        })
                        if status not in ['AWAITING_SHIPMENT', 'CANCELLED']:
                            order_id.action_confirm()
                            order_id.action_confirm()
                        
                # if sale_order_vals:
                #     self.env['sale.order'].sudo().create(sale_order_vals)
        except Exception as e:
            if self._context.get('bypass_error', False):
                pass
            else:
                raise UserError(e)
            
        action_dict = self.env["ir.actions.act_window"]._for_xml_id(
            "sale.action_quotations_with_onboarding"
        )
        return action_dict

    #cron setup ecommerce level == none
    def cron_set_ecommerce_level(self):
        orders = self.env['sale.order'].sudo().search([])
        for order in orders:
            order.ecommerce_level = None 
        return True
    