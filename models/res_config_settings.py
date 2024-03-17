# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    token_tiktok = fields.Char('Access Token TikTok', 
        config_parameter='odoo_tiktok.token_tiktok')
    url_tiktok = fields.Char('Base URL TikTok', 
        config_parameter='odoo_tiktok.url_tiktok')
    shipping_type = fields.Selection([
        ('TIKTOK', 'TIKTOK'),
        ('OTHER', 'OTHER')
    ], string='Shipping Type', default='TIKTOK', config_parameter='odoo_tiktok.shipping_type')
    pricelist_id = fields.Many2one('product.pricelist', 
        'Pricelist for TikTok', config_parameter='odoo_tiktok.pricelist_id')
    shop_id = fields.Char('Shop ID', config_parameter='odoo_tiktok.shop_id')