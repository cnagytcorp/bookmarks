from .conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

import itertools
import json
import requests as req

from premium.utils import is_premium, premium_check
from .utils import page_utils, collection_utils, bookmark_utils, general_utils
from .forms import (AddNewPageForm, EditPageForm, AddBookmarkForm,
                    EditBookmarkForm, MoveBookmarkForm, ImportUrlForm)
from .models import Bookmark, Collection, Page


# views
@login_required
def links(request, page):
    # check page exists, redirect if not
    try:
        page = Page.objects.get(user=request.user, name=page)
    except ObjectDoesNotExist:
        messages.error(
            request, f"Could not find a page with the name '{page}'"
        )
        return redirect('start_app')

    collections = Collection.objects.filter(
        user__username=request.user,
        page__name=page.name
        ).order_by('position')

    bookmarks = Bookmark.objects.filter(
        user__username=request.user,
        collection__in=collections
        )

    # forms
    add_new_page_form = AddNewPageForm(
        current_user=request.user, prefix='new_page', auto_id=False
    )
    edit_page_form = EditPageForm(
        current_user=request.user
    )

    # add new page form
    if 'add-page-form' in request.POST:
        # check allowed extra page at current membership level
        check = premium_check(request, Page, settings.LINKS_STND_MAX_PAGES)

        if check:
            form_data = AddNewPageForm(
                request.POST, current_user=request.user,
                prefix='new_page', auto_id=False)
            if form_data.is_valid():
                new_page = page_utils.add_page(request, form_data)
                return redirect('links', page=new_page)

            else:
                add_new_page_form = form_data
        else:
            return redirect('premium')

    # edit page form
    if 'edit-page-form' in request.POST:
        form_data = EditPageForm(request.POST, current_user=request.user)
        if form_data.is_valid():
            new_page_name = form_data.cleaned_data.get('name')
            page_utils.edit_page_name(request, new_page_name, page)
            return redirect('links', page=new_page_name)

        else:
            edit_page_form = form_data

    # delete page form
    if 'delete-page-form' in request.POST:
        page_utils.delete_page(request, page)

        # if no pages left, create a default page & redirect to it
        if not Page.objects.filter(user=request.user).exists():
            page_utils.create_default_page(request)

        # redirect to first page
        page = Page.objects.get(user=request.user, position=1)
        return redirect('links', page=page)

    # add new collection form
    if 'add-collection' in request.POST:
        # check allowed extra collection at current membership level
        check = premium_check(
            request, Collection, settings.LINKS_STND_MAX_COLLECTIONS)

        if check:
            # check name is allowed and if so, add to db
            proposed_name = request.POST.get('collection_name')
            if collection_utils.validate_name(
                    request, proposed_name, collections, page):
                collection_utils.add_collection(request, page)

            return redirect('links', page=page)
        else:
            return redirect('premium')

    # rename collection form
    if 'rename-collection-form' in request.POST:
        collection_position = request.POST.get('collection-position')
        proposed_name = request.POST.get('new-collection-name')

        if collection_utils.validate_name(
                request, proposed_name, collections, page):
            collection_to_rename = get_object_or_404(
                Collection, user=request.user,
                page=page,
                position=int(collection_position)
            )
            collection_to_rename.name = proposed_name
            collection_to_rename.save()
        return redirect('links', page=page)

    # delete collection form
    if 'delete-collection-form' in request.POST:
        collection_utils.delete_collection(request, page, collections)
        return redirect('links', page=page)

    # delete bookmark form
    if 'delete-bookmark-form' in request.POST:
        bookmark_utils.delete_bookmark(request)
        return redirect('links', page=page)

    # get page names for sidebar
    all_pages = Page.objects.filter(user=request.user).order_by('position')

    # generate collection names & order
    num_of_columns = page.num_of_columns
    collection_list = collection_utils.make_collection_list(
        request, page, num_of_columns, collections)

    # create list of sort options
    sort_options = ['position', 'title', '-title',
                    'added', '-added', 'updated', '-updated']

    # iterate through collection names and create a qs of bookmarks for each
    bm_data = []
    for x in range(num_of_columns):
        column = {}
        for j in (collection_list[x]):
            qs = bookmarks.filter(
                collection=j).order_by(sort_options[j.sort_order])
            column[j] = qs
        bm_data.append(column)

    # Check if no collections on current page
    no_collections = True if collections.count() == 0 else False

    # set this page as the last page visited
    request.session['last_page'] = page.name

    context = {"column_width": 100 / num_of_columns,
               "num_of_columns": num_of_columns,
               "bm_data": bm_data,
               "page": page.name,
               "all_page_names": all_pages,
               "add_new_page_form": add_new_page_form,
               "edit_page_form": edit_page_form,
               "no_collections": no_collections, }
    context = is_premium(request.user, context)

    return render(request, 'links/links.html', context)


@login_required
def start_app(request):
    # check if user has at least 1 page and if not, create one & redirect to it
    if not Page.objects.filter(user=request.user).exists():
        page_utils.create_default_page(request)

    # get last page data and redirect if applicable, otherwise load first page
    try:
        last_page = request.session['last_page']

    except KeyError:
        last_page = Page.objects.get(user=request.user, position=1)
        request.session['last_page'] = last_page.name

    return redirect('links', page=last_page)


@login_required
def change_num_columns(request, page, num):

    # check page exists, redirect if not
    try:
        page = Page.objects.get(user=request.user, name=page)
    except ObjectDoesNotExist:
        messages.error(
            request, f"Could not find a page with the name '{page}'"
        )
        return redirect('start_app')

    page = get_object_or_404(
        Page, user=request.user, name=page
    )

    if int(num) > 0 and int(num) < 6:
        page.num_of_columns = num
        page.save()
    return redirect('links', page=page.name)


@login_required
def page_sort(request):
    # get and format new page order
    data = request.POST.get('new_page_order', None)

    # redirect if user attempts to access view directly
    if data is None:
        return redirect('start_app')

    new_order = list(map(int, data.split(',')))

    original_page_order = Page.objects.filter(
        user=request.user).order_by('position')

    page_limit = settings.LINKS_PREM_MAX_PAGES

    # re-order pages based on user sort
    data = general_utils.qs_sort(
        original_page_order, new_order, page_limit)

    return JsonResponse(data)


@login_required
def bookmark_sort_manual(request):
    data = request.POST.get('new_bookmark_order', None)
    collection_name = request.POST.get('collection_name', None)
    page_name = request.POST.get('page_name', None)

    # redirect if user attempts to access view directly
    if data is None:
        return redirect('start_app')

    new_order = list(map(int, data.split(',')))

    # get collection bookmarks, in original order
    collections = Collection.objects.filter(
        user__username=request.user,
        page__name=page_name
        ).order_by('position')
    original_bookmark_order = Bookmark.objects.filter(
        user__username=request.user,
        collection__in=collections,
        collection__name=collection_name
        ).order_by('position')

    bookmark_limit = settings.LINKS_PREM_MAX_BOOKMARKS

    # re-order bookmarks based on user sort
    data = general_utils.qs_sort(
        original_bookmark_order, new_order, bookmark_limit)

    return JsonResponse(data)


@login_required
def arrange_collections(request, page):

    # check page exists, redirect if not
    try:
        page = Page.objects.get(user=request.user, name=page)
    except ObjectDoesNotExist:
        messages.error(
            request, f"Could not find a page with the name '{page}'"
        )
        return redirect('start_app')

    collections = Collection.objects.filter(
        user__username=request.user).filter(
        page__name=page.name
        ).order_by('position')

    # get page names for sidebar
    all_pages = Page.objects.filter(user=request.user).order_by('position')

    num_of_columns = page.num_of_columns

    # generate collection names & order
    collection_list = collection_utils.make_collection_list(
        request, page, num_of_columns, collections)

    context = {"page": page.name,
               "num_of_columns": num_of_columns,
               "column_width": 100 / num_of_columns,
               "all_page_names": all_pages,
               "collection_data": collection_list, }
    context = is_premium(request.user, context)

    return render(request, 'links/arrange_collections.html', context)


@login_required
def collection_sort(request, page):
    # check page exists, redirect if not
    try:
        page = Page.objects.get(user=request.user, name=page)
    except ObjectDoesNotExist:
        messages.error(
            request, f"Could not find a page with the name '{page}'"
        )
        return redirect('start_app')

    # get collections
    collections = Collection.objects.filter(
        user__username=request.user).filter(
        page__name=page.name
        ).order_by('position')

    post_data = request.POST.get('new_collection_order', None)
    jdata = json.loads(post_data)

    # convert posted data to a list in same format as collection_order_[i]
    raw_collection_order = []
    for x in range(len(jdata)):
        raw_collection_order.append(jdata[x].split(','))
        for y in range(len(raw_collection_order[x])):
            if raw_collection_order[x][y] != '':
                raw_collection_order[x][y] = int(raw_collection_order[x][y])
            else:
                raw_collection_order[x].pop(y)

    # flatten raw collection order
    flattened_raw = list(itertools.chain(*raw_collection_order))

    # update page positions for items inside of collection
    for idx, i in enumerate((collections), 1):
        i.position = flattened_raw.index(idx) + 1
        i.save()

    # get collection / element number that is being moved
    collection_to_move = int((
        request.POST.get('collection_id', None)).replace('_.', ''))

    # to identify which column a collection should move to, use 'dest_contains'
    # this picks a collection in the destination column, so when moving a
    # collection, it's target will be the column containing this collection.
    empty_column_num = 0
    for col in range(len(raw_collection_order)):
        if collection_to_move in raw_collection_order[col]:
            dest_contains_list = raw_collection_order[col]
            # if destination column is empty (the 1 is the item being moved in)
            if len(dest_contains_list) == 1:
                dest_contains = 0
                empty_column_num = col + 1
            # store a collection number from destination column for the
            # collection being moved. This allows us to iterate through
            # columns, looking for this collection, and when found, put
            # the collection being moved into the same column.
            elif dest_contains_list[0] != collection_to_move:
                dest_contains = dest_contains_list[0]
            else:
                dest_contains = dest_contains_list[1]

    # update all collection_order_[i] fields
    new_collection_orders = []
    for i in range(2, 6):
        collection_order = json.loads(
            eval('page.collection_order_'+str(i)))

        # remove 'collection_to_move' from current position
        for col in range(len(collection_order)):
            if collection_to_move in collection_order[col]:
                collection_order[col].remove(collection_to_move)

        # if moving to an already populated column
        if dest_contains:
            for col in range(len(collection_order)):
                if dest_contains in collection_order[col]:
                    collection_order[col].append(collection_to_move)
        else:
            # insert collection into blank column
            insert_position = i if empty_column_num > i else empty_column_num
            collection_order[insert_position - 1].append(collection_to_move)

        # sort all collection_order_[i] lists into 1-n order
        count = 1
        for col in range(len(collection_order)):
            for pos in range(len(collection_order[col])):
                collection_order[col][pos] = count
                count += 1

        new_collection_orders.append(collection_order)

    # # save new page collection orders to db
    page.collection_order_2 = new_collection_orders[0]
    page.collection_order_3 = new_collection_orders[1]
    page.collection_order_4 = new_collection_orders[2]
    page.collection_order_5 = new_collection_orders[3]
    page.save()

    data = {'success': True}
    return JsonResponse(data)


@login_required
def add_bookmark(request, page):
    # check page exists, redirect to page at position 1 if not
    try:
        page = Page.objects.get(user=request.user, name=page)
    except ObjectDoesNotExist:
        page = Page.objects.get(user=request.user, position=1)
        return redirect('add_bookmark', page=page)

    num_collections = Collection.objects.filter(
        user=request.user, page=page).count()
    if num_collections == 0:
        messages.error(
            request, f"Create a collection for your bookmark first")
        return redirect('links', page=page)

    add_bookmark_form = AddBookmarkForm(request.user, page)

    if 'add-bm-form' in request.POST:
        # check allowed extra bookmark at current membership level
        check = premium_check(
            request, Bookmark, settings.LINKS_STND_MAX_BOOKMARKS)

        if check:
            add_bookmark_form = AddBookmarkForm(
                request.user, page, request.POST)

            if add_bookmark_form.is_valid():
                form = add_bookmark_form.save(commit=False)

                form.user = request.user

                # set position value to next highest value. ie, last on list
                max_pos_value = Bookmark.objects.filter(
                    user__username=request.user,
                    collection__id=request.POST['collection']).aggregate(
                        Max('position')
                )

                form.position = 1 if not max_pos_value['position__max'] else \
                    max_pos_value['position__max'] + 1

                if not form.description:
                    form.description = "No description found"

                add_bookmark_form.save()

                return redirect('links', page=page)
        else:
            return redirect('premium')

    else:
        add_bookmark_form = AddBookmarkForm(request.user, page)

    # get page names for sidebar
    all_pages = Page.objects.filter(user=request.user).order_by('position')

    context = {"page": page.name,
               "all_page_names": all_pages,
               "add_bookmark_form": add_bookmark_form}
    context = is_premium(request.user, context)

    return render(request, 'links/add_bookmark.html', context)


@login_required
def manual_url_scrape(request):

    url = request.POST.get('urlToScrape', None)

    # redirect if user attempts to access view directly
    if url is None:
        return redirect('start_app')

    data = bookmark_utils.scrape_url(request, url)

    return JsonResponse(data)


@login_required
def edit_bookmark(request, page, bookmark):

    # check page exists, redirect if not
    try:
        page = Page.objects.get(user=request.user, name=page)
    except ObjectDoesNotExist:
        messages.error(
            request, f"Could not find a page with the name '{page}'"
        )
        return redirect('start_app')

    try:
        bookmark_to_edit = Bookmark.objects.get(user=request.user, pk=bookmark)
    except ObjectDoesNotExist:
        # stop users trying to edit bookmarks that aren't theirs
        messages.error(
            request, f"Could not find the requested bookmark"
        )
        return redirect('start_app')

    edit_bookmark_form = EditBookmarkForm(instance=bookmark_to_edit)

    if 'edit-bm-form' in request.POST:
        edit_bookmark_form = EditBookmarkForm(
            request.POST, instance=bookmark_to_edit)

        if edit_bookmark_form.is_valid():
            edit_bookmark_form.save()
            return redirect('links', page=page)

    # get page names for sidebar
    all_pages = Page.objects.filter(user=request.user).order_by('position')

    context = {"page": page.name,
               "bookmark": bookmark_to_edit,
               "edit_bookmark_form": edit_bookmark_form,
               "all_page_names": all_pages,
               }
    context = is_premium(request.user, context)

    return render(request, 'links/edit_bookmark.html', context)


@login_required
def check_valid_url(request):

    url = request.POST.get('urlToCheck', None)

    # redirect if user attempts to access view directly
    if url is None:
        return redirect('start_app')

    data = {}

    if not url:
        return JsonResponse(data)

    try:
        response = req.head(url)
        response.raise_for_status()

    except req.exceptions.RequestException:
        data['result'] = False

    else:
        data['result'] = True

    return JsonResponse(data)


@login_required
def move_bookmark(request, page, bookmark):

    try:
        page = Page.objects.get(user=request.user, name=page)
    except ObjectDoesNotExist:
        messages.error(
            request, f"Could not find a page with the name '{page}'"
        )
        return redirect('start_app')

    try:
        bookmark_to_move = Bookmark.objects.get(user=request.user, pk=bookmark)
    except ObjectDoesNotExist:
        # stop users trying to move bookmarks that aren't theirs
        messages.error(
            request, f"Could not find the requested bookmark"
        )
        return redirect('start_app')

    # get page names for sidebar
    all_pages = Page.objects.filter(user=request.user).order_by('position')

    move_bookmark_form = MoveBookmarkForm(
        request.user, page, initial={'dest_page': page})

    if 'move-bm-form' in request.POST:
        page = Page.objects.get(
            user=request.user, pk=request.POST.get('dest_page')
        )

        move_bookmark_form = MoveBookmarkForm(request.user, page, request.POST)

        if move_bookmark_form.is_valid():

            orig_collection = bookmark_to_move.collection

            dest_collection = Collection.objects.get(
                id=request.POST.get('dest_collection'))

            # get new position value for bookmark
            dest_position = Bookmark.objects.filter(
                user=request.user, collection=dest_collection
            ).count() + 1

            # update bookmark object with new collection & position
            bookmark_to_move.collection = dest_collection
            bookmark_to_move.position = dest_position
            bookmark_to_move.save()

            # Reapply position values to bookmarks in the original collection
            # to account for the gap made when moving the bookmark out
            orig_collection_to_reorder = Bookmark.objects.filter(
                user=request.user, collection=orig_collection
            ).order_by('position')
            bookmark_utils.reorder_bookmarks(orig_collection_to_reorder)

            return redirect('links', page=page)

        else:
            context = {"page": page.name,
                       "bookmark": bookmark_to_move,
                       "move_bookmark_form": move_bookmark_form,
                       "all_page_names": all_pages,
                       }
            context = is_premium(request.user, context)

            return render(request, 'links/move_bookmark.html', context)

    context = {"page": page.name,
               "bookmark": bookmark_to_move,
               "move_bookmark_form": move_bookmark_form,
               "all_page_names": all_pages,
               }
    context = is_premium(request.user, context)

    return render(request, 'links/move_bookmark.html', context)


@login_required
def update_collection_list(request):
    """
    Get a page.id from POST and use it to generate html of collection
    names and values for the 'dest_collection' dropdown list.
    """

    page_id = request.POST.get('newPagePk')

    # redirect if user attempts to access view directly
    if page_id is None:
        return redirect('start_app')

    new_page = get_object_or_404(
        Page, user=request.user, id=page_id
    )

    new_collections = Collection.objects.filter(
        user=request.user, page=new_page
    ).order_by('position')

    # build a dict of collection pk's and names
    new_collections_dict = {}
    for collection in new_collections:
        new_collections_dict[collection.pk] = collection

    # add the new collection data to an html string
    html = ''
    for k, v in new_collections_dict.items():
        html += f'<option value="{k}">{v}</option>'

    data = {'success': True, 'html': html}
    return JsonResponse(data)


@login_required
def import_url(request):

    url_to_save = request.GET.get('url')

    # redirect if user attempts to access view directly
    if url_to_save is None:
        return redirect('start_app')

    # get page position 1 to set as default in dest_page choice field
    page = Page.objects.get(
        user=request.user, position=1
    )

    # on form post
    if 'import-url-form' in request.POST:
        page = Page.objects.get(
            user=request.user, pk=request.POST.get('dest_page')
        )
        import_url_form = ImportUrlForm(request.POST)
        move_bookmark_form = MoveBookmarkForm(request.user, page, request.POST)

        if import_url_form.is_valid() and move_bookmark_form.is_valid():

            form = import_url_form.save(commit=False)
            form.user = request.user

            dest_collection = Collection.objects.get(
                id=request.POST.get('dest_collection'))

            form.collection = dest_collection

            # get new position value for bookmark
            dest_position = Bookmark.objects.filter(
                user=request.user, collection=dest_collection
            ).count() + 1

            form.position = dest_position
            form.save()

            # TODO NEEDED?
            page = Page.objects.get(
                id=request.POST.get('dest_page')
            )

            request.session['imported_url'] = url_to_save

            # return render(request, 'links/import_url_success.html')
            return redirect('import_url_success')

        else:
            # import_url_form = import_url_form
            # move_bookmark_form = move_bookmark_form

            context = {'import_url_form': import_url_form,
                       'move_bookmark_form': move_bookmark_form,
                       }
            context = is_premium(request.user, context)

            return render(request, 'links/import_url.html', context)

    scrape_data = bookmark_utils.scrape_url(request, url_to_save)

    import_url_form = ImportUrlForm(initial={
        'url': url_to_save,
        'title': scrape_data['title'],
        'description': scrape_data['description']
    })
    move_bookmark_form = MoveBookmarkForm(
        request.user, page)

    context = {'import_url_form': import_url_form,
               'move_bookmark_form': move_bookmark_form,
               }
    context = is_premium(request.user, context)

    return render(request, 'links/import_url.html', context)


@login_required
def import_url_success(request):

    try:
        url = request.session['imported_url']
    except KeyError:
        return redirect('start_app')

    url = request.session['imported_url']
    context = {'url': url}
    del request.session['imported_url']

    return render(request, 'links/import_url_success.html', context)


@login_required
def change_collection_display(request):
    # Update the specified collections display mode

    # get posted data
    collection_id = request.POST.get('collection', None)
    display_mode = request.POST.get('mode', None)

    # redirect if user attempts to access view directly
    if collection_id is None:
        return redirect('start_app')

    # check this view is being accessed correctly
    if collection_id is None or display_mode is None:
        page = general_utils.set_page_name(request)
        return redirect('links', page=page)

    collection = Collection.objects.get(
        user=request.user, id=collection_id
    )

    collection.display_mode = int(display_mode)
    collection.save()

    data = {}
    return JsonResponse(data)


@login_required
def update_sort_order(request, page, collection, sort):

    try:
        page = Page.objects.get(user=request.user, name=page)
    except ObjectDoesNotExist:
        messages.error(
            request, f"Could not find a page with the name '{page}'"
        )
        return redirect('start_app')

    try:
        collection = Collection.objects.get(
            user=request.user, page=page, name=collection
        )
    except ObjectDoesNotExist:
        # stop users trying to move bookmarks that aren't theirs
        messages.error(
            request, f"Could not find the requested collection"
        )
        return redirect('start_app')

    if int(sort) < 0 or int(sort) > 6:
        messages.error(
            request, f"Incorrect sort value - \
                should be an integer between 0 and 6"
        )
        return redirect('start_app')

    collection.sort_order = int(sort)
    collection.save()

    return redirect('links', page=page)


@login_required
def custom_message(request, page, message):
    page = Page.objects.get(
        user=request.user, name=page
    )
    messages.success(
        request, message
    )
    return redirect('links', page=page)
