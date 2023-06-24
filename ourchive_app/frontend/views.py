from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, logout, login
from django.contrib import messages
from .search_models import SearchObject
from html import escape
from django.http import HttpResponse, FileResponse
import logging
from .api_utils import do_get, do_post, do_patch, do_delete, process_results, validate_captcha

logger = logging.getLogger(__name__)


def group_tags(tags):
	tag_parent = {}
	for tag in tags:
		if tag['tag_type'] not in tag_parent:
			tag_parent[tag['tag_type']] = [tag]
		else:
			tag_parent[tag['tag_type']].append(tag)
	return tag_parent


def group_tags_for_edit(tags, tag_types=None):
	tag_parent = {tag_type['label']:{'admin_administrated': tag_type['admin_administrated']} for tag_type in tag_types['results']}
	for tag in tags:
		tag['text'] = escape(tag['text'])
		if 'tags' not in tag_parent[tag['tag_type']]:
			tag_parent[tag['tag_type']]['tags'] = []
			tag_parent[tag['tag_type']]['tags'].append(tag)
		else:
			tag_parent[tag['tag_type']]['tags'].append(tag)
	return tag_parent


def process_attributes(obj_attrs, all_attrs):
	obj_attrs = [attribute['name'] for attribute in obj_attrs]
	for attribute in all_attrs:
		for attribute_value in attribute['attribute_values']:
			if attribute_value['name'] in obj_attrs:
				attribute_value['checked'] = True
	return all_attrs


def get_attributes_from_form_data(request):
	obj_attributes = []
	attributes = request.POST.getlist('attributevals')
	for attribute in attributes:
		attribute_vals = attribute.split('|_|')
		if len(attribute_vals) > 1:
			obj_attributes.append({
				"attribute_type": attribute_vals[0],
				"name": attribute_vals[1]
			})
	return obj_attributes


def get_attributes_for_display(obj_attrs):
	attrs = {}
	attr_types = set()
	for attribute in obj_attrs:
		if attribute['attribute_type'] not in attr_types:
			attr_types.add(attribute['attribute_type'])
			attrs[attribute['attribute_type']] = []
		attrs[attribute['attribute_type']].append(attribute['display_name'])
	return attrs


def sanitize_rich_text(rich_text):
	if rich_text is not None:
		rich_text = escape(rich_text)
	else:
		rich_text = ''
	return rich_text


def get_work_obj(request, work_id=None):
	work_dict = request.POST.copy()
	tags = []
	tag_types = {}
	chapters = []
	result = do_get(f'api/tagtypes', request)[0]['results']
	for item in result:
		tag_types[item['label']] = item
	for item in request.POST:
		if 'tags' in request.POST[item]:
			tag = {}
			json_item = request.POST[item].split("_")
			tag['tag_type'] = json_item[2]
			tag['text'] = json_item[1]
			tags.append(tag)
			work_dict.pop(item)
		elif 'chapters_' in item and work_id is not None:
			chapter_id = item[9:]
			chapter_number = request.POST[item]
			chapters.append({'id': chapter_id, 'number': chapter_number, 'work': work_id})
	work_dict["tags"] = tags
	comments_permitted = work_dict["comments_permitted"]
	work_dict["comments_permitted"] = comments_permitted == "All" or comments_permitted == "Registered users only"
	work_dict["anon_comments_permitted"] = comments_permitted == "All"
	redirect_toc = work_dict.pop('redirect_toc')[0]
	work_dict["is_complete"] = "is_complete" in work_dict
	work_dict["draft"] = "draft" in work_dict
	work_dict = work_dict.dict()
	work_dict["user"] = str(request.user)
	work_dict["attributes"] = get_attributes_from_form_data(request)
	return [work_dict, redirect_toc, chapters]


def get_bookmark_obj(request):
	bookmark_dict = request.POST.copy()
	tags = []
	tag_types = {}
	result = do_get(f'api/tagtypes', request)[0]['results']
	for item in result:
		tag_types[item['label']] = item
	for item in request.POST:
		if 'tags' in request.POST[item]:
			tag = {}
			json_item = request.POST[item].split("_")
			tag['tag_type'] = json_item[2]
			tag['text'] = json_item[1]
			tags.append(tag)
			bookmark_dict.pop(item)
	bookmark_dict["tags"] = tags
	comments_permitted = bookmark_dict["comments_permitted"]
	bookmark_dict["comments_permitted"] = comments_permitted == "All" or comments_permitted == "Registered users only"
	bookmark_dict["anon_comments_permitted"] = comments_permitted == "All"
	bookmark_dict = bookmark_dict.dict()
	bookmark_dict["user"] = str(request.user)
	bookmark_dict["draft"] = 'draft' in bookmark_dict
	bookmark_dict["attributes"] = get_attributes_from_form_data(request)
	return bookmark_dict


def get_bookmark_collection_obj(request):
	collection_dict = request.POST.copy()
	tags = []
	bookmarks = []
	tag_types = {}
	result = do_get(f'api/tagtypes', request)[0]['results']
	for item in result:
		tag_types[item['label']] = item
	for item in request.POST:
		if 'tags' in request.POST[item]:
			tag = {}
			json_item = request.POST[item].split("_")
			tag['tag_type'] = json_item[2]
			tag['text'] = json_item[1]
			tags.append(tag)
			collection_dict.pop(item)
		if 'bookmarks' in request.POST[item]:
			json_item = request.POST[item].split("_")
			bookmark_id = json_item[1]
			bookmarks.append(bookmark_id)
			collection_dict.pop(item)
	collection_dict["tags"] = tags
	collection_dict["bookmarks"] = bookmarks
	comments_permitted = collection_dict["comments_permitted"]
	collection_dict["comments_permitted"] = comments_permitted == "All" or comments_permitted == "Registered users only"
	collection_dict["anon_comments_permitted"] = comments_permitted == "All"
	collection_dict = collection_dict.dict()
	collection_dict["user"] = str(request.user)
	collection_dict["draft"] = 'draft' in collection_dict
	collection_dict["is_private"] = False
	collection_dict["attributes"] = get_attributes_from_form_data(request)
	return collection_dict


def referrer_redirect(request, alternate_url=None):
	if request.META.get('HTTP_REFERER') is not None:
		if '/login' not in request.META['HTTP_REFERER'] and '/register' not in request.META['HTTP_REFERER'] and '/reset' not in request.META['HTTP_REFERER']:
			return redirect(request.META.get('HTTP_REFERER'))
		else:
			refer = alternate_url if alternate_url is not None else '/'
			return redirect(refer)


def get_object_tags(parent):
	for item in parent:
		item['tags'] = group_tags(item['tags']) if 'tags' in item else {}
	return parent


def get_works_list(request, username=None):
	url = f'api/users/{username}/works' if username is not None else f'api/works'
	response = do_get(url, request, params=request.GET)
	result_message = process_results(response, 'works')
	if result_message != 'OK':
		messages.add_message(request, messages.ERROR, result_message, 'get-works-list-error')
		return redirect('/')
	else:
		works = response[0]['results']
		works = get_object_tags(works)
	return {'works': works, 'next_params': response['next_params'] if 'next_params' in response else None, 'prev_params': response['prev_params'] if 'prev_params' in response else None}


def index(request):
	return render(request, 'index.html', {
		'heading_message': 'Welcome to Ourchive',
		'long_message': 'Ourchive is a configurable, extensible, multimedia archive, meant to serve as a modern alternative to PHP-based archives. You can search for existing works, create your own, or create curated collections of works you\'ve enjoyed. Have fun with it!',
		'root': settings.ALLOWED_HOSTS[0],
		'stylesheet_name': 'ourchive-light.css',
		'has_notifications': request.session.get('has_notifications')
	})


def accept_cookies(request):
	if request.user.is_authenticated:
		do_patch(f'api/users/{request.user.id}/', request, data={'id': request.user.id, 'cookies_accepted': True})
	return HttpResponse('')


def content_page(request, pk):
	response = do_get(f'api/contentpages/{pk}', request, params=request.GET)
	return render(request, 'content_page.html', {
		'content_page': response[0]
	})


def user_name(request, username):
	user = do_get(f"api/users/{username}", request)[0]
	if len(user['results']) > 0:
		work_params = {}
		bookmark_params = {}
		bookmark_collection_params = {}
		anchor = None
		if 'work_offset' in request.GET:
			work_params['offset'] = request.GET['work_offset']
			work_params['limit'] = request.GET['work_limit']
			anchor = "work_tab"
		if 'bookmark_offset' in request.GET:
			bookmark_params['offset'] = request.GET['bookmark_offset']
			bookmark_params['limit'] = request.GET['bookmark_limit']
			anchor = "bookmark_tab"
		if 'bookmark_collection_offset' in request.GET:
			bookmark_collection_params['offset'] = request.GET['bookmark_collection_offset']
			bookmark_collection_params['limit'] = request.GET['bookmark_collection_limit']
			anchor = "bookmark_collection_tab"
		works_response = do_get(f'api/users/{username}/works', request, params=work_params)[0]
		works = works_response['results']
		works = get_object_tags(works)
		work_next = f'/username/{username}/{works_response["next_params"].replace("limit=", "work_limit=").replace("offset=", "work_offset=")}' if works_response["next_params"] is not None else None
		work_previous = f'/username/{username}/{works_response["prev_params"].replace("limit=", "work_limit=").replace("offset=", "work_offset=")}' if works_response["prev_params"] is not None else None
		bookmarks_response = do_get(f'api/users/{username}/bookmarks', request, params=bookmark_params)[0]
		bookmarks = bookmarks_response['results']
		bookmark_next = f'/username/{username}/{bookmarks_response["next_params"].replace("limit=", "bookmark_limit=").replace("offset=", "bookmark_offset=")}' if bookmarks_response["next_params"] is not None else None
		bookmark_previous = f'/username/{username}/{bookmarks_response["prev_params"].replace("limit=", "bookmark_limit=").replace("offset=", "bookmark_offset=")}' if bookmarks_response["prev_params"] is not None else None
		bookmarks = get_object_tags(bookmarks)
		bookmark_collection_response = do_get(f'api/users/{username}/bookmarkcollections', request, params=bookmark_collection_params)[0]
		bookmark_collection = bookmark_collection_response['results']
		bookmark_collection_next = f'/username/{username}/{bookmark_collection_response["next_params"].replace("limit=", "bookmark_collection_limit=").replace("offset=", "bookmark_collection_offset=")}' if bookmark_collection_response["next_params"] is not None else None
		bookmark_collection_previous = f'/username/{username}/{bookmark_collection_response["prev_params"].replace("limit=", "bookmark_collection_limit=").replace("offset=", "bookmark_collection_offset=")}' if bookmark_collection_response["prev_params"] is not None else None
		bookmark_collection = get_object_tags(bookmark_collection)
		user = user['results'][0]
		user['attributes'] = get_attributes_for_display(user['attributes'])
		return render(request, 'user.html', {
			'bookmarks': bookmarks,
			'bookmarks_next': bookmark_next,
			'bookmarks_previous': bookmark_previous,
			'user_filter': username,
			'root': settings.ALLOWED_HOSTS[0],
			'works': works,
			'anchor': anchor,
			'works_next': work_next,
			'works_previous': work_previous,
			'bookmark_collections': bookmark_collection,
			'bookmark_collections_next': bookmark_collection_next,
			'bookmark_collections_previous': bookmark_collection_previous,
			'user': user
		})
	else:
		messages.add_message(request, messages.ERROR, 'User not found.', 'user-not-found-error')
		return redirect('/')


def user_block_list(request, username):
	blocklist = do_get(f'api/users/{username}/userblocks', request)
	if blocklist[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to view this blocklist.', 'blocklist-unauthorized-eror')
		return redirect(f'/username/{username}')
	return render(request, 'user_block_list.html', {
		'blocklist': blocklist[0]['results'],
		'username': username
	})


def block_user(request, username):
	data = {'user': request.user.username, 'blocked_user': username}
	blocklist = do_post(f'api/userblocks', request, data)
	if blocklist[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to view this blocklist.', 'blocklist-unauthorized-eror')
	if blocklist[1] >= 200 and blocklist[1] < 300:
		messages.add_message(request, messages.SUCCESS, 'User blocked.')
	return redirect(f'/username/{username}')


def unblock_user(request, username, pk):
	blocklist = do_delete(f'api/userblocks/{pk}', request)
	if blocklist[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to unblock this user.', 'unblock-unauthorized-error')
	if blocklist[1] >= 200 and blocklist[1] < 300:
		messages.add_message(request, messages.SUCCESS, 'User unblocked.', 'unblock-success')
	return redirect(f'/username/{username}')


def report_user(request, username):
	if request.method == 'POST':
		report_data = request.POST.copy()
		# we don't want to let the user specify this
		report_data['user'] = request.user.username
		response = do_post(f'api/userreports/', request, data=report_data)
		if response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'Report created. You should hear from a mod shortly if any more information is required.', 'user-report-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to report this user.', 'user-report-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while reporting this user. Please contact your administrator.', 'user-report-error')
		return redirect(f'/username/{username}/')
	else:
		if request.user.is_authenticated:
			report_reasons = do_get(f'api/reportreasons/', request)[0]
			return render(request, 'user_report_form.html', {
				'reported_user': username,
				'form_title': 'Report User',
				'report_reasons': report_reasons['reasons']
			})
		else:
			messages.add_message(request, messages.ERROR, 'You must log in to perform this action.', 'report-user-unauthorized-error')
			return redirect('/login')


def user_works(request, username):
	works = get_works_list(request, username)
	return render(request, 'works.html', {
		'works': works['works'],
		'next': f"/username/{username}/works/{works['next_params']}" if works["next_params"] is not None else None,
		'previous': f"/username/{username}/works/{works['prev_params']}" if works["prev_params"] is not None else None,
		'user_filter': username,
		'root': settings.ALLOWED_HOSTS[0]})


def user_works_drafts(request, username):
	response = do_get(f'api/users/{username}works/drafts', request)[0]
	works = response['results']
	works = get_object_tags(works)
	return render(request, 'works.html', {
		'works': works,
		'user_filter': username,
		'root': settings.ALLOWED_HOSTS[0]})


def edit_account(request, username):
	if request.method == 'POST':
		user_data = request.POST.copy()
		profile_id = user_data['id']
		user_data.pop('id')
		response = do_patch(f'api/users/{profile_id}/', request, data=user_data)
		if response[1] == 200:
			messages.add_message(request, messages.SUCCESS, 'Account information updated.', 'account-update-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to update this account.', 'account-update-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while updating this account. Please contact your administrator.', 'account-update-error')
		return redirect('/username/{username}')
	else:
		if request.user.is_authenticated:
			response = do_get(f'api/users/{username}', request)[0]
			user = response['results']
			if len(user) > 0:
				user = user[0]
				return render(request, 'account_form.html', {'user': user})
			else:
				messages.add_message(request, messages.ERROR, 'User information not found. Please contact your administrator.', 'user-info-not-found-error')
				return redirect(f'/username/{username}')
		else:
			messages.add_message(request, messages.ERROR, 'You must log in as this user to perform this action.', 'user-info-unauthorized-error')
			return redirect('/login')


def edit_user(request, username):
	if request.method == 'POST':
		user_data = request.POST.copy()
		if user_data['icon'] == "":
			user_data['icon'] = user_data['unaltered_icon']
		user_data.pop('unaltered_icon')
		user_id = user_data.pop('user_id')[0]
		user_data["attributes"] = get_attributes_from_form_data(request)
		response = do_patch(f'api/users/{user_id}/', request, data=user_data)
		if response[1] == 200 or response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'User profile updated.', 'user-profile-update-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to update this user profile.', 'user-profile-update-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while updating this user profile. Please contact your administrator.', 'user-profile-update-error')
		return redirect(f'/username/{username}/')
	else:
		if request.user.is_authenticated:
			response = do_get(f'api/users/{username}', request)
			user = response[0]['results']
			if len(user) > 0:
				user = user[0]
				if user is not None:
					user['profile'] = sanitize_rich_text(user['profile'])
				user_attributes = do_get(f'api/attributetypes', request, params={'allow_on_user': True})
				user['attribute_types'] = process_attributes(user['attributes'], user_attributes[0]['results'])
				return render(request, 'user_form.html', {'user': user, 'form_title': 'Edit User'})
			else:
				messages.add_message(request, messages.ERROR, 'User information not found. Please contact your administrator.', 'user-profile-not-found-error')
				return redirect(f'/username/{username}')
		else:
			messages.add_message(request, messages.ERROR, 'You must log in as this user to perform this action.', 'user-profile-unauthorized-error')
			return redirect('/login')


def delete_user(request, username):
	if not request.user.is_authenticated:
		if 'HTTP_REFERER' in request.META and 'delete' not in request.META.get('HTTP_REFERER'):
			return referrer_redirect(request)
		else:
			if 'delete' not in request.META.get('HTTP_REFERER') and 'account/edit' not in request.META.get('HTTP_REFERER'):
				# you get to the button through the account edit screen, so we don't want to flash a warning if they came through here
				messages.add_message(request, messages.WARNING, 'You are not authorized to view this page.', 'account-delete-unauthorized-error')
			return redirect('/')
	elif request.method == 'POST':
		do_delete(f'api/users/{request.user.id}', request)
		messages.add_message(request, messages.SUCCESS, 'Account deleted successfully.', 'account-delete-success')
		return referrer_redirect(request)
	else:
		return render(request, 'delete_account.html', {'user': request.user})


def user_bookmarks(request, username):
	response = do_get(f'api/users/{username}/bookmarks', request, params=request.GET)[0]
	bookmarks = response['results']
	bookmarks = get_object_tags(bookmarks)
	return render(request, 'bookmarks.html', {
		'bookmarks': bookmarks,
		'next': f"/username/{username}/bookmarks/{response['next_params']}" if response["next_params"] is not None else None,
		'previous': f"/username/{username}/bookmarks/{response['prev_params']}" if response["prev_params"] is not None else None,
		'user_filter': username})


def user_bookmark_collections(request, username):
	response = do_get(f'api/users/{username}/bookmarkcollections', request, params=request.GET)[0]
	bookmark_collections = response['results']
	bookmark_collections = get_object_tags(bookmark_collections)
	return render(request, 'bookmark_collections.html', {
		'bookmark_collections': bookmark_collections,
		'next': f"/username/{username}/bookmarkcollections/{response['next_params']}" if response["next_params"] is not None else None,
		'previous': f"/username/{username}/bookmarkcollections/{response['prev_params']}" if response["prev_params"] is not None else None,
		'user_filter': username})


def user_notifications(request, username):
	response = do_get(f'api/users/{username}/notifications', request, params=request.GET)
	if response[1] == 204 or response[1] == 200:
		notifications = response[0]['results']
		return render(request, 'notifications.html', {
			'notifications': notifications,
			'next': f"/username/{username}/notifications/{response[0]['next_params']}" if response[0]['next_params'] is not None else None,
			'previous': f"/username/{username}/notifications/{response[0]['prev_params']}" if response[0]['prev_params'] is not None else None})
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to view these notifications.', 'notification-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while fetching notifications. Please contact your administrator.', 'notification-fetch-error')
	return redirect(f'/')


def delete_notification(request, username, notification_id):
	response = do_delete(f'api/notifications/{notification_id}', request)
	if response[1] == 204:
		messages.add_message(request, messages.SUCCESS, 'Notification deleted.')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to delete this notification.', 'notification-delete-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while deleting this notification. Please contact your administrator.', 'notification-delete-error')
	return redirect(f'/username/{username}/notifications')


def mark_notification_read(request, username, notification_id):
	data = {'id': notification_id, 'read': True}
	response = do_patch(f'api/notifications/{notification_id}/', request, data=data)
	if response[1] == 200:
		messages.add_message(request, messages.SUCCESS, 'Notification marked as read.', 'notification-read-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to modify this notification.', 'notification-read-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while modifying this notification. Please contact your administrator.', 'notification-read-error')
	return redirect(f'/username/{username}/notifications')


def user_bookmarks_drafts(request, username):
	response = do_get(f'api/users/{username}/bookmarks/drafts', request)
	bookmarks = response[0]['results']
	bookmarks = get_object_tags(bookmarks)
	return render(request, 'bookmarks.html', {'bookmarks': bookmarks, 'user_filter': username})


def search(request):
	if 'term' in request.GET:
		term = request.GET['term']
	else:
		term = request.POST['term']
	request_builder = SearchObject()
	request_object = request_builder.with_term(term)
	response_json = do_post(f'api/search/', request, data=request_object)[0]
	works = response_json['results']['work']
	works = get_object_tags(works)
	bookmarks = response_json['results']['bookmark']
	bookmarks = get_object_tags(bookmarks)
	tags = group_tags(response_json['results']['tag'])
	tag_count = len(response_json['results']['tag'])
	users = response_json['results']['user']
	return render(request, 'search_results.html', {
		'works': works, 'bookmarks': bookmarks,
		'tags': tags, 'users': users, 'tag_count': tag_count,
		'facets': response_json['results']['facet'],
		'root': settings.ALLOWED_HOSTS[0], 'term': term})


def tag_autocomplete(request):
	term = request.GET.get('text')
	params = {'term': term}
	params['type'] = request.GET.get('type') if 'type' in request.GET else ''
	params['fetch_all'] = request.GET.get('fetch_all') if 'fetch_all' in request.GET else ''
	response = do_get(f'api/tag-autocomplete', request, params)
	template = 'tag_autocomplete.html' if request.GET.get('source') == 'search' else 'edit_tag_autocomplete.html'
	return render(request, template, {
		'tags': response[0]['results'],
		'fetch_all': params['fetch_all']})


def bookmark_autocomplete(request):
	term = request.GET.get('text')
	params = {'term': term}
	response = do_get(f'api/bookmark-autocomplete', request, params)
	template = 'bookmark_collection_autocomplete.html'
	return render(request, template, {
		'bookmarks': response[0]['results']})


def search_filter(request):
	term = request.POST['term']
	request_builder = SearchObject()
	request_object = request_builder.with_term(term)
	for key in request.POST:
		filter_val = request.POST[key]
		if filter_val == 'csrfmiddlewaretoken':
			continue
		if filter_val == 'term':
			continue
		else:
			filter_options = key.split('|')
			for option in filter_options:
				filter_details = option.split('$')
				filter_type = request_builder.get_object_type(filter_details[0])
				if filter_type == 'work':
					if len(request_object['work_search']['filter'][filter_details[0]]) > 0:
						request_object['work_search']['filter'][filter_details[0]].append(filter_details[1])
					else:
						request_object['work_search']['filter'][filter_details[0]] = []
						request_object['work_search']['filter'][filter_details[0]].append(filter_details[1])
				elif filter_type == 'tag':
					tag_type = filter_details[0].split(',')[1]
					tag_text = filter_details[1].split(',')[1]
					request_object['tag_search']['filter']['tag_type'].append(tag_type)
					request_object['tag_search']['filter']['text'].append(tag_text)
				elif filter_type == 'bookmark':
					if len(request_object['bookmark_search']['filter'][filter_details[0]]) > 0:
						request_object['bookmark_search']['filter'][filter_details[0]].append(filter_details[1])
					else:
						request_object['bookmark_search']['filter'][filter_details[0]] = []
						request_object['bookmark_search']['filter'][filter_details[0]].append(filter_details[1])
	response_json = do_post(f'api/search/', request, data=request_object)[0]
	works = response_json['results']['work']
	works = get_object_tags(works)
	bookmarks = response_json['results']['bookmark']
	bookmarks = get_object_tags(bookmarks)
	tags = group_tags(response_json['results']['tag'])
	tag_count = len(response_json['results']['tag'])
	users = response_json['results']['user']
	return render(request, 'search_results.html', {
		'works': works, 'bookmarks': bookmarks,
		'tags': tags, 'users': users, 'tag_count': tag_count,
		'facets': response_json['results']['facet'],
		'root': settings.ALLOWED_HOSTS[0], 'term': term})


@require_http_methods(["GET"])
def works(request):
	works_response = do_get(f'api/works/', request, params=request.GET)[0]
	works = works_response['results']
	works = get_object_tags(works)
	for work in works:
		work['attributes'] = get_attributes_for_display(work['attributes'])
	return render(request, 'works.html', {
		'works': works,
		'next': f"/works/{works_response['next_params']}" if works_response['next_params'] is not None else None,
		'previous': f"/works/{works_response['prev_params']}" if works_response['prev_params'] is not None else None,
		'root': settings.ALLOWED_HOSTS[0]})


def works_by_type(request, type_id):
	response = do_get(f'api/worktypes/{type_id}/works', request)[0]
	works = response['results']
	works = get_object_tags(works)
	return render(request, 'works.html', {
		'works': works,
		'root': settings.ALLOWED_HOSTS[0]})


def new_work(request):
	work_types = do_get(f'api/worktypes', request)[0]
	if request.user.is_authenticated and request.method != 'POST':
		work = {'title': 'Untitled Work', 'user': request.user.username}
		tag_types = do_get(f'api/tagtypes', request)[0]
		tags = {result['label']:[] for result in tag_types['results']}
		work_attributes = do_get(f'api/attributetypes', request, params={'allow_on_work': True})
		work['attribute_types'] = process_attributes([], work_attributes[0]['results'])
		return render(request, 'work_form.html', {
			'tags': tags,
			'form_title': 'New Work',
			'work_types': work_types['results'],
			'work': work})
	elif request.user.is_authenticated:
		work_data = get_work_obj(request)
		work = do_post(f'api/works/', request, work_data[0])[0]
		if work_data[1] == 'false':
			return redirect(f'/works/{work["id"]}')
		else:
			return redirect(f'/works/{work["id"]}/chapters/new?count=0')
	else:
		messages.add_message(request, messages.ERROR, 'You must log in to post a new work.', 'new-work-unauthorized-error')
		return redirect('/login')


def new_chapter(request, work_id):
	if request.user.is_authenticated and request.method != 'POST':
		count = request.GET.get('count') if request.GET.get('count') != '' else 0
		chapter = {'title': 'Untitled Chapter', 'work': work_id, 'text': '', 'number': int(count) + 1}
		chapter_attributes = do_get(f'api/attributetypes', request, params={'allow_on_chapter': True})
		chapter['attribute_types'] = process_attributes([], chapter_attributes[0]['results'])
		return render(request, 'chapter_form.html', {
			'chapter': chapter,
			'form_title': 'New Chapter'})
	elif request.user.is_authenticated:
		chapter_dict = request.POST.copy()
		chapter_dict["draft"] = "draft" in chapter_dict
		chapter_dict["attributes"] = get_attributes_from_form_data(request)
		response = do_post(f'api/chapters/', request, data=chapter_dict)
		if response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'Chapter created.', 'chapter-created-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to create this chapter.', 'chapter-create-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while updating this chapter. Please contact your administrator.', 'chapter-create-error')
		redirect_url = f'/works/{work_id}/?offset={request.GET.get("from_work", 0)}' if 'from_work' in request.GET else f"/works/{work_id}/edit/#work-form-chapter-content-parent"
		return redirect(redirect_url)
	else:
		messages.add_message(request, messages.ERROR, 'You must log in to post a new chapter.', 'chapter-create-login-error')
		return redirect('/login')


def edit_chapter(request, work_id, id):
	if request.method == 'POST':
		chapter_dict = request.POST.copy()
		chapter_dict["draft"] = "draft" in chapter_dict
		chapter_dict["attributes"] = get_attributes_from_form_data(request)
		response = do_patch(f'api/chapters/{id}/', request, data=chapter_dict)
		if response[1] == 200:
			messages.add_message(request, messages.SUCCESS, 'Chapter updated.', 'chapter-update-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to update this chapter.', 'chapter-update-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while updating this chapter. Please contact your administrator.', 'chapter-update-error')
		redirect_url = f'/works/{work_id}/?offset={request.GET.get("from_work", 0)}' if 'from_work' in request.GET else f"/works/{work_id}/edit/#work-form-chapter-content-parent"
		return redirect(redirect_url)
	else:
		if request.user.is_authenticated:
			chapter = do_get(f'api/chapters/{id}', request)[0]
			chapter['text'] = sanitize_rich_text(chapter['text'])
			chapter['text'] = chapter['text'].replace('\r\n', '<br/>')
			chapter['summary'] = sanitize_rich_text(chapter['summary'])
			chapter['notes'] = sanitize_rich_text(chapter['notes'])
			chapter_attributes = do_get(f'api/attributetypes', request, params={'allow_on_chapter': True})
			chapter['attribute_types'] = process_attributes(chapter['attributes'], chapter_attributes[0]['results'])
			return render(request, 'chapter_form.html', {
				'chapter': chapter,
				'form_title': 'Edit Chapter'})
		else:
			messages.add_message(request, messages.ERROR, 'You must log in to perform this action.', 'chapter-update-login-error')
			return redirect('/login')


def edit_work(request, id):
	if request.method == 'POST':
		work_dict = get_work_obj(request, id)
		chapters = work_dict[2]
		response = do_patch(f'api/works/{id}/', request, data=work_dict[0])
		if response[1] == 200:
			for chapter in chapters:
				response = do_patch(f'api/chapters/{chapter["id"]}/', request, data=chapter)
			messages.add_message(request, messages.SUCCESS, 'Work updated.', 'work-update-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to update this work.', 'work-update-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while updating this work. Please contact your administrator.', 'work-update-error')
		if work_dict[1] == 'false':
			return redirect(f'/works/{id}')
		else:
			return redirect(f'/works/{id}/chapters/new?count={len(chapters)}')
	else:
		if request.user.is_authenticated:
			work_types = do_get(f'api/worktypes', request)[0]
			tag_types = do_get(f'api/tagtypes', request)[0]
			work = do_get(f'api/works/{id}/', request)
			result_message = process_results(work, 'work')
			if result_message != 'OK':
				messages.add_message(request, messages.ERROR, result_message, 'work-update-fetch-error')
				return redirect('/')
			work = work[0]
			work['summary'] = sanitize_rich_text(work['summary'])
			work['notes'] = sanitize_rich_text(work['notes'])
			work_attributes = do_get(f'api/attributetypes', request, params={'allow_on_work': True})
			work['attribute_types'] = process_attributes(work['attributes'], work_attributes[0]['results'])
			chapters = do_get(f'api/works/{id}/chapters/all', request)[0]
			tags = group_tags_for_edit(work['tags'], tag_types) if 'tags' in work else []
			return render(request, 'work_form.html', {
				'work_types': work_types['results'],
				'form_title': 'Edit Work',
				'work': work,
				'tags': tags,
				'show_chapter': request.GET.get('show_chapter') if 'show_chapter' in request.GET else None,
				'chapters': chapters,
				'chapter_count': len(chapters)})
		else:
			messages.add_message(request, messages.ERROR, 'You must log in to perform this action.', 'work-update-login-error')
			return redirect('/login')


def publish_work(request, id):
	data = {'id': id, 'draft': False}
	response = do_patch(f'api/works/{id}/', request, data=data)
	if response[1] == 200:
		messages.add_message(request, messages.SUCCESS, 'Work published.', 'work-publish-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to update this work.', 'work-publish-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while updating this work. Please contact your administrator.', 'work-publish-error')
	return redirect(f'/works/{id}')


def export_work(request, pk, file_ext):
	file_url = do_get(f'api/works/{pk}/export/', request, params={'extension': file_ext})
	if file_url[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to export this work.', 'work-export-unauthorized-error')
	if file_url[1] == 404:
		messages.add_message(request, messages.ERROR, 'Work export not found.', 'work-export-not-found-error')
	elif file_url[1] >= 400:
		error_message = f'{file_url[0]["message"]}' if 'message' in file_url[0] else 'An error occurred exporting this work. Please contact your administrator.'
		messages.add_message(request, messages.ERROR, error_message, 'work-export-error')
		return redirect(f'/works/{pk}')
	response = FileResponse(open(file_url[0]['media_url'], 'rb'))
	return response


def publish_chapter(request, work_id, chapter_id):
	data = {'id': chapter_id, 'draft': False}
	response = do_patch(f'api/chapters/{chapter_id}/', request, data=data)
	if response[1] == 200:
		messages.add_message(request, messages.SUCCESS, 'Chapter published.', 'chapter-publish-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to update this chapter.', 'chapter-publish-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while updating this chapter. Please contact your administrator.', 'chapter-publish-error')
	return redirect(f'/works/{work_id}')


def publish_work_and_chapters(request, id):
	data = {'id': id, 'draft': False}
	response = do_patch(f'api/works/{id}/publish-full/', request, data=data)
	if response[1] == 200:
		messages.add_message(request, messages.SUCCESS, 'Work and all chapters published.', 'work-publish-all-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to update this work.', 'work-publish-all-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while updating this work. Please contact your administrator.', 'work-publish-all-error')
	return redirect(f'/works/{id}')


def publish_bookmark(request, id):
	data = {'id': id, 'draft': False}
	response = do_patch(f'api/bookmarks/{id}/', request, data=data)
	if response[1] == 200:
		messages.add_message(request, messages.SUCCESS, 'Bookmark published.', 'bookmark-publish-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to update this bookmark.', 'bookmark-publish-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while updating this bookmark. Please contact your administrator.', 'bookmark-publish-error')
	return redirect(f'/bookmarks/{id}')


def new_fingerguns(request, work_id):
	data = {'work': str(work_id), 'user': request.user.username}
	response = do_post(f'api/fingerguns/', request, data=data)
	if response[1] == 201:
		messages.add_message(request, messages.SUCCESS, 'Fingerguns added.', 'fingergun-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to add fingerguns to this work.', 'fingergun-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while adding fingerguns to this work. Please contact your administrator.', 'fingergun-error')
	return redirect(f'/works/{work_id}')


def delete_work(request, work_id):
	response = do_delete(f'api/works/{work_id}/', request)
	if response[1] == 204:
		messages.add_message(request, messages.SUCCESS, 'Work deleted.', 'work-delete-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to delete this work.', 'work-delete-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while deleting this work. Please contact your administrator.', 'work-delete-error')
	return referrer_redirect(request)


def delete_chapter(request, work_id, chapter_id):
	response = do_delete(f'api/chapters/{chapter_id}/', request)
	if response[1] == 204:
		messages.add_message(request, messages.SUCCESS, 'Chapter deleted.', 'chapter-delete-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to delete this chapter.', 'chapter-delete-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while deleting this chapter. Please contact your administrator.', 'chapter-delete-error')
	return redirect(f'/works/{work_id}/edit/?show_chapter=true')


def new_bookmark(request, work_id):
	if request.user.is_authenticated and request.method != 'POST':
		bookmark = {'title': '', 'description': '', 'user': request.user.username, 'work': {'title': request.GET.get('title'), 'id': work_id}, 'is_private': True, 'rating': 5}
		bookmark_attributes = do_get(f'api/attributetypes', request, params={'allow_on_bookmark': True})
		bookmark['attribute_types'] = process_attributes([], bookmark_attributes[0]['results'])
		tag_types = do_get(f'api/tagtypes', request)[0]
		tags = {result['label']:[] for result in tag_types['results']}
		star_count = do_get(f'api/bookmarks', request)[0]['star_count']
		return render(request, 'bookmark_form.html', {
			'tags': tags,
			'rating_range': star_count,
			'form_title': 'New Bookmark',
			'bookmark': bookmark})
	elif request.user.is_authenticated:
		bookmark_dict = get_bookmark_obj(request)
		response = do_post(f'api/bookmarks/', request, data=bookmark_dict)
		if response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'Bookmark created.', 'bookmark-create-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to create this bookmark.', 'bookmark-create-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while creating this bookmark. Please contact your administrator.', 'bookmark-create-error')
		return redirect(f'/bookmarks/{response[0]["id"]}')
	else:
		messages.add_message(request, messages.ERROR, 'You must log in to create a bookmark.', 'bookmark-create-login-error')
		return redirect('/login')


def edit_bookmark(request, pk):
	if request.method == 'POST':
		bookmark_dict = get_bookmark_obj(request)
		response = do_patch(f'api/bookmarks/{pk}/', request, data=bookmark_dict)
		if response[1] == 200:
			messages.add_message(request, messages.SUCCESS, 'Bookmark updated.', 'bookmark-update-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to update this bookmark.', 'bookmark-update-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while updating this bookmark. Please contact your administrator.', 'bookmark-update-error')
		return redirect(f'/bookmarks/{pk}')
	else:
		if request.user.is_authenticated:
			tag_types = do_get(f'api/tagtypes', request)[0]
			bookmark = do_get(f'api/bookmarks/{pk}/draft', request)[0]
			bookmark['description'] = sanitize_rich_text(bookmark['description'])
			bookmark_attributes = do_get(f'api/attributetypes', request, params={'allow_on_bookmark': True})
			bookmark['attribute_types'] = process_attributes(bookmark['attributes'], bookmark_attributes[0]['results'])
			tags = group_tags_for_edit(bookmark['tags'], tag_types) if 'tags' in bookmark else []
			return render(request, 'bookmark_form.html', {
				'rating_range': bookmark['star_count'],
				'form_title': 'Edit Bookmark',
				'bookmark': bookmark,
				'tags': tags})
		else:
			messages.add_message(request, messages.ERROR, 'You must log in to perform this action.', 'bookmark-update-login-error')
			return redirect('/login')


def delete_bookmark(request, bookmark_id):
	response = do_delete(f'api/bookmarks/{bookmark_id}/', request)
	if response[1] == 204:
		messages.add_message(request, messages.SUCCESS, 'Bookmark deleted.', 'bookmark-delete-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to delete this bookmark.', 'bookmark-delete-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while deleting this bookmark. Please contact your administrator.', 'bookmark-delete-error')
	if str(bookmark_id) in request.META.get('HTTP_REFERER'):
		return redirect('/bookmarks')
	return referrer_redirect(request)


def bookmark_collections(request):
	response = do_get(f'api/bookmarkcollections/', request)[0]
	bookmark_collections = response['results']
	bookmark_collections = get_object_tags(bookmark_collections)
	for bkcol in bookmark_collections:
		bkcol['attributes'] = get_attributes_for_display(bkcol['attributes'])
	return render(request, 'bookmark_collections.html', {
		'bookmark_collections': bookmark_collections,
		'next': f"/bookmarkcollections/{response['next_params']}" if response['next_params'] is not None else None,
		'previous': f"/bookmarkcollections/{response['prev_params']}" if response['prev_params'] is not None else None,
		'root': settings.ALLOWED_HOSTS[0]})


def new_bookmark_collection(request):
	if request.user.is_authenticated and request.method != 'POST':
		bookmark_collection = {'title': 'New Bookmark Collection', 'description': '', 'user': request.user.username, 'is_private': True, 'is_draft': True}
		bookmark_collection_attributes = do_get(f'api/attributetypes', request, params={'allow_on_bookmark_collection': True})
		bookmark_collection['attribute_types'] = process_attributes([], bookmark_collection_attributes[0]['results'])
		tag_types = do_get(f'api/tagtypes', request)[0]
		tags = {result['label']:[] for result in tag_types['results']}
		return render(request, 'bookmark_collection_form.html', {
			'tags': tags,
			'form_title': 'New Bookmark Collection',
			'bookmark_collection': bookmark_collection})
	elif request.user.is_authenticated:
		collection_dict = get_bookmark_collection_obj(request)
		response = do_post(f'api/bookmarkcollections/', request, data=collection_dict)
		if response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'Bookmark collection created.', 'bookmark-collection-create-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to create this bookmark collection.', 'bookmark-collection-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while creating this bookmark collection. Please contact your administrator.', 'bookmark-collection-error')
		return redirect(f'/bookmark-collections/{response[0]["id"]}')
	else:
		messages.add_message(request, messages.ERROR, 'You must log in to create a bookmark collection.', 'bookmark-collection-login-error')
		return redirect('/login')


def edit_bookmark_collection(request, pk):
	if request.method == 'POST':
		collection_dict = get_bookmark_collection_obj(request)
		response = do_patch(f'api/bookmarkcollections/{pk}/', request, data=collection_dict)
		if response[1] == 200:
			messages.add_message(request, messages.SUCCESS, 'Bookmark collection updated.', 'bookmark-collection-update-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to update this bookmark collection.', 'bookmark-collection-update-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while updating this bookmark collection. Please contact your administrator.', 'bookmark-collection-update-error')
		return redirect(f'/bookmark-collections/{pk}')
	else:
		if request.user.is_authenticated:
			tag_types = do_get(f'api/tagtypes', request)[0]
			bookmark_collection = do_get(f'api/bookmarkcollections/{pk}/', request)[0]
			bookmark_collection['description'] = sanitize_rich_text(bookmark_collection['description'])
			bookmark_attributes = do_get(f'api/attributetypes', request, params={'allow_on_bookmark_collection': True})
			bookmark_collection['attribute_types'] = process_attributes(bookmark_collection['attributes'], bookmark_attributes[0]['results'])
			tags = group_tags_for_edit(bookmark_collection['tags'], tag_types) if 'tags' in bookmark_collection else []
			return render(request, 'bookmark_collection_form.html', {
				'bookmark_collection': bookmark_collection,
				'form_title': 'Edit Bookmark Collection',
				'tags': tags})
		else:
			messages.add_message(request, messages.ERROR, 'You must log in to perform this action.', 'bookmark-collection-update-login-error')
			return redirect('/login')


def bookmark_collection(request, pk):
	bookmark_collection = do_get(f'api/bookmarkcollections/{pk}', request)[0]
	tags = group_tags(bookmark_collection['tags']) if 'tags' in bookmark_collection else {}
	bookmark_collection['attributes'] = get_attributes_for_display(bookmark_collection['attributes'])
	comment_offset = request.GET.get('comment_offset') if request.GET.get('comment_offset') else 0
	if 'comment_thread' in request.GET:
		comment_id = request.GET.get('comment_thread')
		comments = do_get(f"api/bookmarkcomments/{comment_id}", request)[0]
		comment_offset = 0
		comments = {'results': [comments], 'count': request.GET.get('comment_count')}
		bookmark_collection['post_action_url'] = f"/bookmarkcollections/{pk}/comments/new?offset={comment_offset}&comment_thread={comment_id}"
		bookmark_collection['edit_action_url'] = f"""/bookmarkcollections/{pk}/comments/edit?offset={comment_offset}&comment_thread={comment_id}"""
	else:
		comments = do_get(f'api/bookmarkcollections/{pk}/comments?limit=10&offset={comment_offset}', request)[0]
		bookmark_collection['post_action_url'] = f"/bookmarkcollections/{pk}/comments/new"
		bookmark_collection['edit_action_url'] = f"""/bookmarkcollections/{pk}/comments/edit"""
	for bookmark in bookmark_collection['bookmarks_readonly']:
		bookmark['description'] = bookmark['description'].replace('<p>', '<br/>').replace('</p>', '').replace('<br/>', '', 1)
	expand_comments = 'expandComments' in request.GET and request.GET['expandComments'].lower() == "true"
	scroll_comment_id = request.GET['scrollCommentId'] if'scrollCommentId' in request.GET else None
	user_can_comment = (bookmark_collection['comments_permitted'] and (bookmark_collection['anon_comments_permitted'] or request.user.is_authenticated)) if 'comments_permitted' in bookmark_collection else False
	return render(request, 'bookmark_collection.html', {
		'bkcol': bookmark_collection,
		'tags': tags,
		'comment_offset': comment_offset,
		'scroll_comment_id': scroll_comment_id,
		'expand_comments': expand_comments,
		'user_can_comment': user_can_comment,
		'comments': comments})


def delete_bookmark_collection(request, pk):
	response = do_delete(f'api/bookmarkcollections/{pk}/', request)
	if response[1] == 204:
		messages.add_message(request, messages.SUCCESS, 'Bookmark collection deleted.', 'bookmark-collection-delete-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to delete this bookmark collection.', 'bookmark-collection-delete-unauthorized-error')
	elif response[1] == 404:
		messages.add_message(request, messages.ERROR, 'Bookmark collection not found.', 'bookmark-collection-delete-not-found-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while deleting this bookmark collection. Please contact your administrator.', 'bookmark-collection-delete-error')
	if request.META is not None and 'HTTP_REFERER' in request.META and str(pk) in request.META.get('HTTP_REFERER'):
		return redirect('/bookmark-collections')
	return referrer_redirect(request)


def publish_bookmark_collection(request, pk):
	data = {'id': pk, 'draft': False}
	response = do_patch(f'api/bookmarkcollections/{pk}/', request, data=data)
	if response[1] == 200:
		messages.add_message(request, messages.SUCCESS, 'Bookmark collection published.', 'bookmark-collection-publish-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to update this bookmark collection.', 'bookmark-collection-publish-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while updating this bookmark collection. Please contact your administrator.', 'bookmark-collection-publish-error')
	return redirect(f'/bookmark-collections/{pk}')


def log_in(request):
	if request.method == 'POST':
		user = authenticate(username=request.POST.get('username').lower(), password=request.POST.get('password'))
		if user is not None:
			login(request, user)
			messages.add_message(request, messages.SUCCESS, 'Login successful.', 'login-success')
			return referrer_redirect(request)
		else:
			messages.add_message(request, messages.ERROR, 'Login unsuccessful. Please try again.', 'login-unsuccessful-error')
			return redirect('/login')
	else:
		if 'HTTP_REFERER' in request.META:
			return render(request, 'login.html', {'referrer': request.META['HTTP_REFERER']})
		else:
			return render(request, 'login.html', {'referrer': '/'})


def reset_password(request):
	if request.method == 'POST':
		user = authenticate(username=request.POST.get('username'), password=request.POST.get('password'))
		if user is not None:
			login(request, user)
			messages.add_message(request, messages.SUCCESS, 'Login successful.', 'reset-login-success')
			return referrer_redirect(request)
		else:
			messages.add_message(request, messages.ERROR, 'Login unsuccessful. Please try again.', 'reset-login-error')
			return redirect('/login')
	else:
		if 'HTTP_REFERER' in request.META:
			return render(request, 'login.html', {
				'referrer': request.META['HTTP_REFERER']})
		else:
			return render(request, 'login.html', {
				'referrer': '/'})


def register(request):
	if request.method == 'POST':
		response = do_post(f'api/users/', request, data=request.POST)
		if response[1] == 200 or response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'Registration successful!', 'register-success')
			return redirect('/login')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'Registration is not permitted at this time. Please contact site admin.', 'register-disabled-error')
			return redirect('/')
		else:
			messages.add_message(request, messages.ERROR, 'Registration unsuccessful. Please try again.', 'register-error')
			return redirect('/login')
	else:
		if 'invite_token' in request.GET:
			response = do_get(f'api/invitations/', request, params={'email': request.GET.get('email'), 'invite_token': request.GET.get('invite_token')})
			if response[1] == 200:
				return render(request, 'register.html', {'permit_registration': True, 'invite_code': response[0]['invitation']})
			else:
				messages.add_message(request, messages.ERROR, 'Your invite code or email is incorrect. Please check your link again and contact site admin.', 'register-invalid-token-error')
				return redirect('/')
		permit_registration = do_get(f'api/settings/', request, params={'setting_name': 'Registration Permitted'})[0]
		invite_only = do_get(f'api/settings', request, params={'setting_name': 'Invite Only'})[0]
		if permit_registration['results'][0]['value'] == "False":
			return render(request, 'register.html', {'permit_registration': False})
		elif invite_only['results'][0]['value'] == "True":
			return redirect('/request-invite')
		else:
			return render(request, 'register.html', {'permit_registration': True})


def request_invite(request):
	if request.method == 'POST':
		response = do_post(f'api/invitations/', request, data=request.POST.copy())
		if response[1] == 200 or response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'You have been added to the invite queue.', 'invite-request-success')
			return render(request, 'request_invite.html', {'invite_sent': True})
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'An error occurred requesting your invite. Please contact site admin.', 'invite-request-error')
			return redirect('/')
		elif response[1] == 418:
			messages.add_message(request, messages.ERROR, 'Your account already exists. Please log in or reset your password.', 'invite-request-dupe-error')
			return redirect('/login')
	else:
		return render(request, 'request_invite.html', {'invite_sent': False})


def log_out(request):
	logout(request)
	messages.add_message(request, messages.SUCCESS, 'Logout successful.', 'logout-success')
	return redirect(request.META['HTTP_REFERER'])


@require_http_methods(["GET"])
def work(request, pk):
	chapter_offset = int(request.GET.get('offset', 0))
	view_full = request.GET.get('view_full', False)
	work_types = do_get(f'api/worktypes', request)[0]
	url = f'api/works/{pk}/'
	work = do_get(url, request)
	result_message = process_results(work, 'work')
	if result_message != 'OK':
		messages.add_message(request, messages.ERROR, result_message, 'work-fetch-error')
		return redirect('/')
	work = work[0]
	tags = group_tags(work['tags']) if 'tags' in work else {}
	work['attributes'] = get_attributes_for_display(work['attributes'])
	chapter_url_string = f'api/works/{pk}/chapters{"?limit=1" if view_full is False else "/all"}'
	if chapter_offset > 0:
		chapter_url_string = f'{chapter_url_string}&offset={chapter_offset}'
	chapter_response = do_get(chapter_url_string, request)[0]
	chapter_json = chapter_response['results'] if 'results' in chapter_response else chapter_response
	user_can_comment = (work['comments_permitted'] and (work['anon_comments_permitted'] or request.user.is_authenticated)) if 'comments_permitted' in work else False
	expand_comments = 'expandComments' in request.GET and request.GET['expandComments'].lower() == "true"
	chapters = []
	for chapter in chapter_json:
		if 'id' in chapter:
			if 'comment_thread' not in request.GET:
				comment_offset = request.GET.get('comment_offset') if request.GET.get('comment_offset') else 0
				chapter_comments = do_get(f"api/chapters/{chapter['id']}/comments?limit=10&offset={comment_offset}", request)[0]
				chapter['post_action_url'] = f"/works/{pk}/chapters/{chapter['id']}/comments/new?offset={chapter_offset}"
				chapter['edit_action_url'] = f"""/works/{pk}/chapters/{chapter['id']}/comments/edit?offset={chapter_offset}"""
			else:
				comment_id = request.GET.get('comment_thread')
				chapter_comments = do_get(f"api/comments/{comment_id}", request)[0]
				comment_offset = 0
				chapter_comments = {'results': [chapter_comments], 'count': request.GET.get('comment_count')}
				chapter['post_action_url'] = f"/works/{pk}/chapters/{chapter['id']}/comments/new?offset={chapter_offset}&comment_thread={comment_id}"
				chapter['edit_action_url'] = f"""/works/{pk}/chapters/{chapter['id']}/comments/edit?offset={chapter_offset}&comment_thread={comment_id}"""
			chapter['comments'] = chapter_comments
			chapter['comment_offset'] = comment_offset
			chapter['attributes'] = get_attributes_for_display(chapter['attributes'])
			chapter['new_action_url'] = f"/works/{pk}/chapters/{chapter['id']}/comments/new?offset={chapter_offset}"
			chapters.append(chapter)
	return render(request, 'work.html', {
		'work_types': work_types['results'],
		'work': work,
		'user_can_comment': user_can_comment,
		'expand_comments': expand_comments,
		'scroll_comment_id': request.GET.get("scrollCommentId") if request.GET.get("scrollCommentId") is not None else None,
		'id': pk,
		'tags': tags,
		'view_full': view_full,
		'root': settings.ALLOWED_HOSTS[0],
		'chapters': chapters,
		'chapter_offset': chapter_offset,
		'next_chapter': f'/works/{pk}?offset={chapter_offset + 1}' if 'next' in chapter_response and chapter_response['next'] else None,
		'previous_chapter': f'/works/{pk}?offset={chapter_offset - 1}' if 'previous' in chapter_response and chapter_response['previous'] else None,})


def render_comments(request, work_id, chapter_id):
	limit = request.GET.get('limit', '')
	offset = request.GET.get('offset', '')
	depth = request.GET.get('depth', 0)
	chapter_offset = request.GET.get('chapter_offset', '')
	comments = do_get(f'api/chapters/{chapter_id}/comments?limit={limit}&offset={offset}', request)[0]
	post_action_url = f"/works/{work_id}/chapters/{chapter_id}/comments/new?offset={chapter_offset}"
	edit_action_url = f"""/works/{work_id}/chapters/{chapter_id}/comments/edit?offset={chapter_offset}"""
	return render(request, 'chapter_comments.html', {
		'comments': comments['results'],
		'current_offset': comments['current'],
		'top_level': 'true',
		'depth': int(depth),
		'chapter_offset': chapter_offset,
		'chapter': {'id': chapter_id},
		'comment_count': comments['count'],
		'next_params': comments['next_params'],
		'prev_params': comments['prev_params'],
		'work': {'id': work_id},
		'post_action_url': post_action_url,
		'edit_action_url': edit_action_url})


def render_bookmark_comments(request, pk):
	limit = request.GET.get('limit', '')
	offset = request.GET.get('offset', '')
	depth = request.GET.get('depth', 0)
	comments = do_get(f'api/bookmarks/{pk}/comments?limit={limit}&offset={offset}', request)[0]
	post_action_url = f"/bookmarks/{pk}/comments/new"
	edit_action_url = f"""/bookmarks/{pk}/comments/edit"""
	return render(request, 'bookmark_comments.html', {
		'comments': comments['results'],
		'current_offset': comments['current'],
		'bookmark': {'id': pk},
		'top_level': 'true',
		'depth': int(depth),
		'comment_count': comments['count'],
		'next_params': comments['next_params'],
		'prev_params': comments['prev_params'],
		'post_action_url': post_action_url,
		'edit_action_url': edit_action_url})


def create_chapter_comment(request, work_id, chapter_id):
	if request.method == 'POST':
		if not request.user.is_authenticated:
			if settings.USE_CAPTCHA:
				captcha_passed = validate_captcha(request)
				if not captcha_passed:
					messages.add_message(request, messages.ERROR, 'Captcha failed. Please try again.', 'captcha-fail-error')
					return redirect(f"/works/{work_id}/")
		comment_dict = request.POST.copy()
		offset_url = int(request.GET.get('offset', 0))
		comment_count = int(request.POST.get('chapter_comment_count'))
		comment_thread = int(request.GET.get('comment_thread')) if 'comment_thread' in request.GET else None
		if comment_count > 10 and request.POST.get('parent_comment') is None:
			comment_offset = int(int(request.POST.get('chapter_comment_count')) / 10) * 10
		elif comment_count > 10 and request.POST.get('parent_comment') is not None:
			comment_offset = request.POST.get('parent_comment_next')
		else:
			comment_offset = 0
		if request.user.is_authenticated:
			comment_dict["user"] = str(request.user)
		else:
			comment_dict["user"] = None
		response = do_post(f'api/comments/', request, data=comment_dict)
		comment_id = response[0]['id'] if 'id' in response[0] else None
		if response[1] == 200 or response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'Comment posted.', 'chapter-comment-post-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to post this comment.', 'chapter-comment-post-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while posting this comment. Please contact your administrator.', 'chapter-comment-post-error')
		if comment_thread is None:
			return redirect(f"/works/{work_id}/?expandComments=true&scrollCommentId={comment_id}&offset={offset_url}&comment_offset={comment_offset}&comment_offset_chapter={chapter_id}")
		else:
			return redirect(f"/works/{work_id}/?expandComments=true&scrollCommentId={comment_id}&offset={offset_url}&comment_thread={comment_thread}&comment_count={comment_count}")


def edit_chapter_comment(request, work_id, chapter_id):
	if request.method == 'POST':
		comment_dict = request.POST.copy()
		offset_url = int(request.GET.get('offset', 0))
		comment_count = int(request.POST.get('chapter_comment_count'))
		comment_thread = int(request.GET.get('comment_thread')) if 'comment_thread' in request.GET else None
		if comment_count > 10 and request.POST.get('parent_comment_val') is None:
			comment_offset = int(int(request.POST.get('chapter_comment_count')) / 10) * 10
		elif comment_count > 10 and request.POST.get('parent_comment_val') is not None:
			comment_offset = request.POST.get('parent_comment_next')
		else:
			comment_offset = 0
		comment_dict.pop('parent_comment_val')
		if request.user.is_authenticated:
			comment_dict["user"] = str(request.user)
		else:
			comment_dict["user"] = None
		response = do_patch(f"api/comments/{comment_dict['id']}/", request, data=comment_dict)
		if response[1] == 200 or response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'Comment edited.', 'chapter-comment-edit-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to post this comment.', 'chapter-comment-edit-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while posting this comment. Please contact your administrator.', 'chapter-comment-edit-error')
		if comment_thread is None:
			return redirect(f"/works/{work_id}/?expandComments=true&scrollCommentId={comment_dict['id']}&offset={offset_url}&comment_offset={comment_offset}&comment_offset_chapter={chapter_id}")
		else:
			return redirect(f"/works/{work_id}/?expandComments=true&scrollCommentId={comment_dict['id']}&offset={offset_url}&comment_thread={comment_thread}&comment_count={comment_count}")
	else:
		messages.add_message(request, messages.ERROR, 'Invalid URL.', 'chapter-comment-edit-not-found')
		return redirect(f'/works/{work_id}')


def delete_chapter_comment(request, work_id, chapter_id, comment_id):
	response = do_delete(f'api/comments/{comment_id}/', request)
	if response[1] == 204:
		messages.add_message(request, messages.SUCCESS, 'Comment deleted.', 'chapter-comment-delete-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to delete this comment.', 'chapter-comment-delete-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while deleting this comment. Please contact your administrator.', 'chapter-comment-delete-error')
	return redirect(f'/works/{work_id}')


def create_bookmark_comment(request, pk):
	if request.method == 'POST':
		if not request.user.is_authenticated:
			if settings.USE_CAPTCHA:
				captcha_passed = validate_captcha(request)
				if not captcha_passed:
					messages.add_message(request, messages.ERROR, 'Captcha failed. Please try again.', 'bookmark-comment-captcha-error')
					return redirect(f"/bookmarks/{pk}/")
		comment_dict = request.POST.copy()
		comment_count = int(request.POST.get('bookmark_comment_count'))
		comment_thread = int(request.GET.get('comment_thread')) if 'comment_thread' in request.GET else None
		if comment_count > 10 and request.POST.get('parent_comment') is None:
			comment_offset = int(int(request.POST.get('bookmark_comment_count')) / 10) * 10
		elif comment_count > 10 and request.POST.get('parent_comment') is not None:
			comment_offset = request.POST.get('parent_comment_next')
		else:
			comment_offset = 0
		if request.user.is_authenticated:
			comment_dict["user"] = str(request.user)
		else:
			comment_dict["user"] = None
		response = do_post(f'api/bookmarkcomments/', request, data=comment_dict)
		comment_id = response[0]['id'] if 'id' in response[0] else None
		if response[1] == 200 or response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'Comment posted.', 'bookmark-comment-post-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to post this comment.', 'bookmark-comment-post-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while posting this comment. Please contact your administrator.', 'bookmark-comment-post-error')
		if comment_thread is None:
			return redirect(f"/bookmarks/{pk}/?expandComments=true&scrollCommentId={comment_id}&comment_offset={comment_offset}")
		else:
			return redirect(f"/bookmarks/{pk}/?expandComments=true&scrollCommentId={comment_id}&comment_thread={comment_thread}&comment_count={comment_count}")


def edit_bookmark_comment(request, pk):
	if request.method == 'POST':
		comment_dict = request.POST.copy()
		comment_count = int(request.POST.get('bookmark_comment_count'))
		if comment_count > 10 and request.POST.get('parent_comment_val') is None:
			comment_offset = int(int(request.POST.get('bookmark_comment_count')) / 10) * 10
		elif comment_count > 10 and request.POST.get('parent_comment_val') is not None:
			comment_offset = request.POST.get('parent_comment_next')
		else:
			comment_offset = 0
		comment_dict.pop('parent_comment_val')
		if request.user.is_authenticated:
			comment_dict["user"] = str(request.user)
		else:
			comment_dict["user"] = None
		response = do_patch(f"api/bookmarkcomments/{comment_dict['id']}/", request, data=comment_dict)
		if response[1] == 200 or response[1] == 201:
			messages.add_message(request, messages.SUCCESS, 'Comment edited.', 'bookmark-comment-edit-success')
		elif response[1] == 403:
			messages.add_message(request, messages.ERROR, 'You are not authorized to post this comment.', 'bookmark-comment-edit-unauthorized-error')
		else:
			messages.add_message(request, messages.ERROR, 'An error has occurred while posting this comment. Please contact your administrator.', 'bookmark-comment-edit-error')
		return redirect(f"/bookmarks/{pk}/?expandComments=true&scrollCommentId={comment_dict['id']}&comment_offset={comment_offset}")
	else:
		messages.add_message(request, messages.ERROR, '404 Page Not Found', 'bookmark-comment-not-found-error')
		return redirect(f'/bookmarks/{pk}')


def delete_bookmark_comment(request, pk, comment_id):
	response = do_delete(f'api/bookmarkcomments/{comment_id}/', request)
	if response[1] == 204:
		messages.add_message(request, messages.SUCCESS, 'Comment deleted.', 'bookmark-comment-delete-success')
	elif response[1] == 403:
		messages.add_message(request, messages.ERROR, 'You are not authorized to delete this comment.', 'bookmark-comment-delete-unauthorized-error')
	else:
		messages.add_message(request, messages.ERROR, 'An error has occurred while deleting this comment. Please contact your administrator.', 'bookmark-comment-delete-error')
	return redirect(f'/bookmarks/{pk}')


def bookmarks(request):
	response = do_get(f'api/bookmarks/', request, params=request.GET)[0]
	bookmarks = response['results']
	previous_param = response['prev_params']
	next_param = response['next_params']
	bookmarks = get_object_tags(bookmarks)
	for bookmark in bookmarks:
		bookmark['attributes'] = get_attributes_for_display(bookmark['attributes'])
	return render(request, 'bookmarks.html', {
		'bookmarks': bookmarks,
		'rating_range': response['star_count'],
		'next': f"/bookmarks/{next_param}" if next_param is not None else None,
		'previous': f"/bookmarks/{previous_param}" if previous_param is not None else None})


def bookmark(request, pk):
	bookmark = do_get(f'api/bookmarks/{pk}', request)[0]
	tags = group_tags(bookmark['tags']) if 'tags' in bookmark else {}
	bookmark['attributes'] = get_attributes_for_display(bookmark['attributes'])
	comment_offset = request.GET.get('comment_offset') if request.GET.get('comment_offset') else 0
	if 'comment_thread' in request.GET:
		comment_id = request.GET.get('comment_thread')
		comments = do_get(f"api/bookmarkcomments/{comment_id}", request)[0]
		comment_offset = 0
		comments = {'results': [comments], 'count': request.GET.get('comment_count')}
		bookmark['post_action_url'] = f"/bookmarks/{pk}/comments/new?offset={comment_offset}&comment_thread={comment_id}"
		bookmark['edit_action_url'] = f"""/bookmarks/{pk}/comments/edit?offset={comment_offset}&comment_thread={comment_id}"""
	else:
		comments = do_get(f'api/bookmarks/{pk}/comments?limit=10&offset={comment_offset}', request)[0]
		bookmark['post_action_url'] = f"/bookmarks/{pk}/comments/new"
		bookmark['edit_action_url'] = f"""/bookmarks/{pk}/comments/edit"""
	expand_comments = 'expandComments' in request.GET and request.GET['expandComments'].lower() == "true"
	scroll_comment_id = request.GET['scrollCommentId'] if'scrollCommentId' in request.GET else None
	user_can_comment = (bookmark['comments_permitted'] and (bookmark['anon_comments_permitted'] or request.user.is_authenticated)) if 'comments_permitted' in bookmark else False
	return render(request, 'bookmark.html', {
		'bookmark': bookmark,
		'tags': tags,
		'comment_offset': comment_offset,
		'scroll_comment_id': scroll_comment_id,
		'expand_comments': expand_comments,
		'user_can_comment': user_can_comment,
		'rating_range': bookmark['star_count'],
		'work': bookmark['work'] if 'work' in bookmark else {},
		'comments': comments})


def works_by_tag(request, pk):
	tagged_works = do_get(f'api/tags/{pk}/works', request)[0]
	tagged_works['results'] = get_object_tags(tagged_works['results'])
	tagged_bookmarks = do_get(f'api/tags/{pk}/bookmarks', request)[0]
	tagged_bookmarks['results'] = get_object_tags(tagged_bookmarks['results'])
	return render(request, 'tag_results.html', {'tag_id': pk, 'works': tagged_works, 'bookmarks': tagged_bookmarks})


def works_by_tag_next(request, tag_id):
	if 'next' in request.GET:
		next_url = request.GET.get('next', '')
	else:
		next_url = request.GET.get('previous', '')
	offset_url = request.GET.get('offset', '')
	works = do_get(f'{next_url}&offset={offset_url}', request)[0]
	return render(request, 'paginated_works.html', {'works': works, 'tag_id': tag_id})


def switch_css_mode(request):
	request.session['css_mode'] = "dark" if request.session.get('css_mode') == "light" or request.session.get('css_mode') is None else "light"
	return referrer_redirect(request)
