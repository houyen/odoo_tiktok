from odoo import models, fields, api
from odoo.exceptions import UserError


class ProductMapping(models.TransientModel):
    _name = 'product.mapping'
    _description = 'Product Mapping'

    @api.model
    def _default_line_ids(self):
        tiktok_product = self.env['tiktok.product'].search([('is_mapping', '=', False)])
        line_ids = []
        for product in tiktok_product:
            line_ids.append((0, 0, {
                'tiktok_product_id': product.id,
            }))
        return line_ids
    
    line_ids = fields.One2many('product.mapping.line', 'line_product_id', 'Product Mapping', default=lambda self: self._default_line_ids())
    
    def action_mapping(self):
        for line in self.line_ids:
            if line.product_id:
                line.tiktok_product_id.write({
                    'is_mapping': True,
                    'product_id': line.product_id.id
                })
                line.product_id.write({
                    'is_mapping': True
                })
            else:
                raise UserError('Please select product for all TikTok products')
        return True
    
    
class ProductMappingLine(models.TransientModel):
    _name = 'product.mapping.line'
    _description = 'Product Mapping Line'

    tiktok_product_id = fields.Many2one('tiktok.product', 'TikTok Product')
    product_id = fields.Many2one('product.product', 'Product')
    line_product_id = fields.Many2one('product.mapping', 'Product Mapping')
    
    