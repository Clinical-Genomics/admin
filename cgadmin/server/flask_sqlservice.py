# -*- coding: utf-8 -*-
from flask import current_app, _app_ctx_stack
from sqlservice import SQLClient


class FlaskSQLService(object):
    """Flask extension for sqlservice.SQLClient instance."""
    def __init__(self,
                 app=None,
                 model_class=None,
                 query_class=None,
                 session_class=None,
                 session_options=None):
        self.app = app
        self.model_class = model_class
        self.query_class = query_class
        self.session_class = session_class

        # Set default scopefunc for SQLAlchemy session as app context stack
        # identifier function. This associates each session with the
        # appropriate Flask app context.
        self.session_options = {'scopefunc': _app_ctx_stack.__ident_func__}
        self.session_options.update(session_options or {})

        if app:
            self.init_app(app)

    def init_app(self, app):
        options = {}

        if self.model_class:
            options['model_class'] = self.model_class

        if self.query_class:
            options['query_class'] = self.query_class

        if self.session_class:
            options['session_class'] = self.session_class

        options['session_options'] = self.session_options

        # Store SQLClient instances on app.extensions so it can be accessed
        # through flask.current_app proxy.
        app.extensions['sqlservice'] = SQLClient(app.config, **options)

        # Ensure that the session is removed on app context teardown so we
        # don't leave any sessions open after the request ends.
        @app.teardown_appcontext
        def shutdown_session(response_or_exc):
            self.remove()
            return response_or_exc

    def __getattr__(self, attr):
        """Proxy attribute access to SQLClient instance."""
        return getattr(current_app.extensions['sqlservice'], attr)
