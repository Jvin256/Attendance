# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name'        : "Purchase Order Approval by Email",
    'author'      : "Ascetic Business Solution LLP",
    'category'    : "Purchase",
    'summary'     : """Purchase Order Approval by Email""",
    'website'     : 'http://www.asceticbs.com',
    'license'     : 'OEEL-1',
    'description' : """ Purchase Order Approval by Email """,
    'version'     : '1.0',
    'depends'     : ['purchase', 'mail', 'website','base','base_automation','account'],
    'data'        : [
                     'security/ir.model.access.csv',
                     'security/approve_po_by_email_security.xml',
                     'data/po_approval_template.xml',
                     'data/order_confirm_reject_template.xml',
                     'data/receive_notification_template.xml',
                     'data/automation.xml',
                     'view/purchase_view.xml',
                     'view/purchase_approval_level_view.xml',
                     'view/purchase_approval_matrix_view.xml',
                    ],
    'installable' : True,
    'application' : True,
    'auto_install': False,
}
