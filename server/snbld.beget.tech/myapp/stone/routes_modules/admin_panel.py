from flask import render_template
from stone.middleware import admin_required
from stone.routes import stone_bp


@stone_bp.route('/admin')
@admin_required
def admin_panel():
    return render_template('stone_admin.html')
