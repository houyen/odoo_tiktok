# -*- coding: utf-8 -*-
{
    "name": "ODOO TikTok",
    # "summary": "",
    "version": "16.0.0.0.0",
    "author":  "houyen",
    # "website": "",
    "category": "Sales",
    "depends": [
        "delivery",
        "sale_management",
        "sale_stock",
    ],
    "data": [
        "data/ir_cron.xml",
        "data/data.xml",
        "security/ir.model.access.csv",
        "views/res_config_setting_views.xml",
        "views/tiktok_product_view.xml",
        "views/sale_order_view.xml",
        "views/sync_tiktok_product_views.xml",
        "wizard/mapping_tiktok_product_view.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
