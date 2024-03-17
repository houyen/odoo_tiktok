import requests

from odoo import fields, models, api
from odoo.tools import config
from .sign_api_request import  get_active_shops

class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    def action_refresh_token_tiktok(self):
        headers = {
            "Content-Type": "application/json",
        }
        url = 'https://auth.tiktok-shops.com/api/v2/token/refresh'
        try:
            app_key = config.get('app_key_tiktok', False)
            refresh_token = config.get('refresh_token_tiktok', False)
            app_secret = config.get('app_secret_tiktok', False)
            params = {
                "app_key": app_key, 
                "app_secret": app_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                }
            res = requests.get(url, params=params, headers=headers, timeout=30)
            result = res.json()
            if result.get('status') == 200:
                self.env['ir.config_parameter'].sudo().set_param('odoo_tiktok.token_tiktok', result.get('data').get('access_token'))
                # self.env['ir.config_parameter'].sudo().set_param('odoo_tiktok.refresh_token_tiktok', result.get('data').get('refresh_token'))
        except Exception:
            pass
        
    def action_get_active_shop(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('odoo_tiktok.url_tiktok', '')
        token = self.env['ir.config_parameter'].sudo().get_param('odoo_tiktok.token_tiktok', '')
        app_key = config.get('app_key_tiktok', False)
        app_secret = config.get('app_secret_tiktok', False)
        try:
            shops = get_active_shops(app_key, app_secret, token, base_url)
            if shops:
                for shop in shops:
                    self.env['ir.config_parameter'].sudo().set_param('odoo_tiktok.shop_id', shop.get("id"))  
        except Exception:
            pass
