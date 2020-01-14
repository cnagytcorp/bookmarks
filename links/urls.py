from django.urls import path

from .views import (start_app, import_url, import_url_success,
                    update_collection_list, page_sort, bookmark_sort_manual,
                    change_collection_display, check_valid_url,
                    manual_url_scrape, links, add_bookmark,
                    arrange_collections, collection_sort, edit_bookmark,
                    move_bookmark, custom_message, update_sort_order)

from .utils import collection_utils


urlpatterns = [
    path('_start-app',
         start_app, name="start_app"),
    path('_import-url/',
         import_url, name="import_url"),
    path('_import-url-success',
         import_url_success, name="import_url_success"),
    path('_update_collection_list',
         update_collection_list, name="update_collection_list"),
    path('_change-num-columns/<page>/<num>',
         collection_utils.change_num_columns, name="change_num_columns"),
    path('_page_sort',
         page_sort, name="page_sort"),
    path('_bookmark_sort_manual',
         bookmark_sort_manual, name="bookmark_sort_manual"),
    path('_change_collection_display',
         change_collection_display, name="change_collection_display"),
    path('_check_valid_url',
         check_valid_url, name="check_valid_url"),
    path('_manual_url_scrape',
         manual_url_scrape, name="manual_url_scrape"),

    path('<page>', links, name="links"),

    path('<page>/add-bookmark',
         add_bookmark, name="add_bookmark"),
    path('<page>/arrange',
         arrange_collections, name="arrange_collections"),
    path('<page>/collection-sort',
         collection_sort, name="collection_sort"),
    path('<page>/<bookmark>/edit-bookmark',
         edit_bookmark, name="edit_bookmark"),
    path('<page>/<bookmark>/move-bookmark',
         move_bookmark, name="move_bookmark"),
    path('<page>/custom_message/<message>',
         custom_message, name="custom_message"),
    path('<page>/<collection>/<sort>/update_sort_order',
         update_sort_order, name='update_sort_order'),
]
