# -*- coding: utf-8 -*-
from odoo import http

# class Addons/plm(http.Controller):
#     @http.route('/addons/plm/addons/plm/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/addons/plm/addons/plm/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('addons/plm.listing', {
#             'root': '/addons/plm/addons/plm',
#             'objects': http.request.env['addons/plm.addons/plm'].search([]),
#         })

#     @http.route('/addons/plm/addons/plm/objects/<model("addons/plm.addons/plm"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('addons/plm.object', {
#             'object': obj
#         })