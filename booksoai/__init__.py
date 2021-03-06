import pymongo
import logging

from datetime import datetime, timedelta

from pyramid.events import NewRequest, NewResponse
from pyramid.config import Configurator

from .sync import do_sync
from .utils import get_db_connection


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('oai_pmh', '/oai-pmh')
    config.add_renderer('oai', factory='booksoai.renderers.oai_factory')

    # Starts sync process on new requests
    def start_sync(event):
        settings = event.request.registry.settings
        if settings.get('auto_sync', False):
            db = event.request.db
            interval = settings.get('auto_sync_interval', 60*60*12)
            try:
                update = db.updates.find_one()
                if update:
                    last_update = update['updated_at']
                    next_update = last_update + timedelta(seconds=int(interval))
                    if next_update < datetime.now():
                        do_sync(settings)
                else:
                    do_sync(settings)
            except pymongo.errors.AutoReconnect as e:
                logging.getLogger(__name__).error('MongoDB: %s' % e.message)


    def create_db_conn(event):
        settings = event.request.registry.settings
        db = get_db_connection(settings)
        event.request.db = db

    def close_db_conn(event):
        event.request.db.connection.close()
     
    config.add_subscriber(create_db_conn, NewRequest)
    config.add_subscriber(close_db_conn, NewResponse)
    config.add_subscriber(start_sync, NewRequest)
    config.scan(ignore='booksoai.tests')
    return config.make_wsgi_app()
