from flask import Flask, render_template, request, url_for, redirect, flash, jsonify

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, list_keywords, List, ListKeyword, HeadingItem
from database_setup import Row, TextEntry, DateEntry, DateTimeEntry, IntegerEntry 
from database_setup import TrueFalse, TimeEntry, Duration, TwoDecimal, LargeDecimal


#Oauth for google steps: 
from flask import session as login_session
import random, string 


from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

engine = create_engine('postgresql+psycopg2://jpsupalist:sup_jpw@localhost/supalist1')
Base.metadata.bind = engine 
DBSession = sessionmaker(bind = engine)
session = DBSession()

app = Flask(__name__)


CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
	#open(r'/var/www/supalist/supalist/client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Supalist_V1"





#user1 = session.query(User).first()
#This is for when I need to access the different data types: 
li_of_dtypes = [TextEntry,IntegerEntry,DateEntry,TrueFalse,TimeEntry,Duration,TwoDecimal,LargeDecimal]
data_types ={}
for i in range(0,8):
	data_types[i] = li_of_dtypes[i]
#This is for when I need to access the TEXT (strings) of the different data types: 
#Note - these should be removed, its ridiculous
li_of_dtypes_str = ["TextEntry","IntegerEntry","DateEntry","TrueFalse","TimeEntry","Duration","TwoDecimal","LargeDecimal"]

#data_types_tuple = [(0, 'TextEntry'),(1,'IntegerEntry'),(2,'DateEntry'),(3,'DateEntry'),(4,'TrueFalse'),(5,'TimeEntry'),(6, 'Duration'),(7,'TwoDecimal'),(8,'LargeDecimal')]
data_types_tuple = [(0, 'TextEntry'),(1,'IntegerEntry'),(2,'DateEntry'),(3,'TrueFalse'),(4,'TimeEntry'),(5, 'Duration'),(6,'TwoDecimal'),(7,'LargeDecimal')]




@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    #return "The current session state is %s" % login_session['state']
    return render_template("login.html", STATE=state)



@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        #oauth_flow = flow_from_clientsecrets(r'/var/www/supalist/supalist/client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
    	#Take this out later? login_session['access_token'] = credentials.access_token   
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # THIS IS NEW CODE FOR ADDING A NEW USER TO USER TABLE
    user_id = getUserID(login_session['email'])
    if not user_id:
    	user_id = createUser(login_session)
    login_session['user_id'] = user_id



    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    #print "done!"
    return output

    # DISCONNECT - Revoke a current user's token and reset their login_session


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    #print 'In gdisconnect access token is %s', access_token
    #print 'User name is: '
    #print login_session['username']
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    #print "url: ", url 
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    #print 'result type:', type(result) , 'result is '
    #print result
    #if result['status'] == '200':
    if result['status'] == '200' or ('must-revalidate' in result['cache-control']):
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        #return response
        return redirect(url_for('Home'))
    else:
        response = make_response(json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response




@app.route('/')
@app.route('/home/', methods = ['GET', 'POST'])
def Home():
	#return "headings of all/ top lists, or of the main menu options"

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']
	all_lists = session.query(List).order_by(List.name).all()
	lists_and_headings = {}    
	for li in all_lists:
		lists_and_headings[li] = session.query(HeadingItem).filter_by(list_id = li.id).all()
	if request.method == 'POST':
		search_str = request.form["srch"]
		return redirect(url_for('Result', search_str = search_str))
	else:
		return render_template('homepage.html', all_lists = all_lists, lists_and_headings = lists_and_headings, logged_in=logged_in, un=un)

#Making an API Enpoint (GET Request)
@app.route('/home/JSON')
def allListsJSON():
	all_lists = session.query(List).order_by(List.name).all()
	lists_and_headings = {}    
	for li in all_lists:
		lists_and_headings[li] = session.query(HeadingItem).filter_by(list_id = li.id).all()
	return jsonify(Lists = [i.serialize for i in all_lists])


@app.route('/results/<string:search_str>/', methods = ['GET', 'POST'])
def Result(search_str):

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	kw_matching_lis = session.query(List).filter(List.l_keywords.any(keyword=search_str)).all()
	lists_and_headings = {}
	for li in kw_matching_lis:
		lists_and_headings[li] = session.query(HeadingItem).filter_by(list_id = li.id).all()

	if request.method == 'POST':
		new_search_str = request.form["srch"]
		return redirect(url_for('Result', search_str = new_search_str))
	return render_template('view_results.html', kw_matching_lis = kw_matching_lis, lists_and_headings = lists_and_headings, 
		search_str = search_str, logged_in=logged_in, un=un)


@app.route('/about/')
def About():

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	return render_template('about.html', logged_in=logged_in, un=un)


@app.route('/new/', methods = ['GET', 'POST'])
def NewList():

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	if request.method == 'POST':
		newli = List(name = request.form['namer'], description = request.form['desc'], votes = 0, user=getUser())
		kw1 = request.form['kw1']
		if kw1 != None:
			newli.l_keywords.append(ListKeyword(keyword = kw1))
		
		kw2 = request.form['kw2']
		if kw2 != None:
			newli.l_keywords.append(ListKeyword(keyword = kw2))

		kw3 = request.form['kw3']
		if kw3 != None:
			newli.l_keywords.append(ListKeyword(keyword = kw3))
		session.add(newli)
		session.commit()
		flash("Well done! You created a new list called: {}".format(newli.name))
		return redirect(url_for('Home'))
	else:
		return render_template('new_list.html', logged_in=logged_in, un=un)

@app.route('/<int:list_id>/details/')
def ListDetails(list_id):

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	li_2_detail = session.query(List).filter_by(id = list_id).one()
	creator = session.query(User).filter_by(id = li_2_detail.user_id).one()
	creators_name = creator.user_name
	num_headings = len(session.query(HeadingItem).filter_by(list_id = list_id).order_by(HeadingItem.id.asc()).all())
	num_entries = len(session.query(Row).filter_by(list_id = list_id).order_by(Row.id.asc()).all())
	return render_template('list_details.html', li_2_detail = li_2_detail, num_headings = num_headings, num_entries = num_entries, 
		logged_in=logged_in, un=un, creators_name=creators_name)


@app.route('/<int:list_id>/edit/', methods = ['GET', 'POST'])
def EditList(list_id):

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	li_2_edit = session.query(List).filter_by(id = list_id).one()
	columns_2_edit = session.query(HeadingItem).filter_by(list_id = list_id).order_by(HeadingItem.id.asc()).all()
	keyword_list = []
	for i in li_2_edit.l_keywords:
		keyword_list.append(i)
	if request.method == 'POST':
		li_2_edit.name = request.form['namer']
		li_2_edit.description = request.form['desc']
		kw1, kw2 = request.form['kw1'], request.form['kw2']
		if kw1 != None and kw1 not in li_2_edit.l_keywords:
			li_2_edit.l_keywords.append(ListKeyword(keyword = kw1))
		if kw2 != None and kw2 not in li_2_edit.l_keywords:
			li_2_edit.l_keywords.append(ListKeyword(keyword = kw2))
		session.add(li_2_edit)
		session.commit()
		flash("Well done! You just edited the following list: {}".format(li_2_edit.name))
		return redirect(url_for('QueryList', list_id = li_2_edit.id))
	else:
		return render_template('edit_list.html', list_id = list_id, lname=li_2_edit, keyword_list=keyword_list
			, logged_in=logged_in, un=un)


@app.route('/<int:list_id>/delete/', methods = ['GET', 'POST'])
def DeleteList(list_id):

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']


	li_2_del = session.query(List).filter_by(id = list_id).one()
	headings2del = session.query(HeadingItem).filter_by(list_id = list_id).all()
	rows_2_del = session.query(Row).filter_by(list_id = list_id).order_by(Row.id.asc()).all()

	if request.method == 'POST':
		#Delete all keywords associated to this list (then entries, then headings, then rows, FINALLY, lists!) :
		li_2_del.l_keywords = []

		#Delete entries from each of the different data type tables: 
		for row in rows_2_del:
			for i in range(0,len(li_of_dtypes)):
				e_2_del = session.query(li_of_dtypes[i]).filter_by(row_id = row.id).all()
				if len(e_2_del) > 0:
					for w in e_2_del:
						session.delete(w)
						session.commit()

		for heading in headings2del:
			session.delete(heading)
			session.commit()

		for row in rows_2_del:
			session.delete(row)
			session.commit()

		session.delete(li_2_del)
		session.commit()
		flash("Damn Son! You just deleted the following list: {}".format(li_2_del.name))


		return redirect(url_for('Home'))
	else:
		return render_template('delete_list.html', li_2_del = li_2_del, list_id = list_id, 
			headings2del = headings2del, no_rows_2_del=len(rows_2_del), logged_in=logged_in, un=un)
	return "Are you sure you want to delete this list? (only certain privileges will allow you to delete a list? - or never?) list{}".format(list_id)

#The following global variables are for ordering the row entries in a list
order_by_heading = 0 #Which heading to order by
rev = 0              #Whether to order ascending or descending

@app.route('/<int:list_id>/', methods = ['GET', 'POST'])
def QueryList(list_id):

	login_session['selected_headings'] = []

	global order_by_heading
	global rev


#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']


	list_to_view = session.query(List).filter_by(id = list_id).first()
	#heading_items = session.query(HeadingItem).filter_by(list_id = list_to_view.id).order_by(asc(HeadingItem.id))
	#  This is the main one heading_items = session.query(HeadingItem).filter_by(list_id = list_to_view.id).order_by(HeadingItem.id.asc())
	heading_items = session.query(HeadingItem).filter_by(list_id = list_to_view.id).order_by(HeadingItem.name.asc())
	rows = session.query(Row).filter_by(list_id = list_to_view.id).order_by(Row.id.asc())
	row_entries = {}

	#Defining the logic determining creator of item (only person allowed to delete)
	owner_id = list_to_view.user_id
	deletable_l = False # This is val passed to template about wether delete button (for lists) will do what's required or popup saying not allowed 
	# to delete because not creator of ths thing (list, heading, row, entry)
	owner = session.query(User).filter_by(id = owner_id).one()
	if owner.user_name == un:
		deletable_l = True

	for row in rows:
		#row_entries[row.id] = session.query(TextEntry).filter_by(row_id = row.id).order_by(TextEntry.heading_id).all()
		row_entries[row.id] = session.query(TextEntry).filter_by(row_id = row.id).order_by(TextEntry.heading_id).all()
		for e in li_of_dtypes[1:]:
			for i in (session.query(e).filter_by(row_id = row.id).all()):
				row_entries[row.id].append(i)
		#(row_entries[row.id]).sort(key=lambda x: int(x.heading_id))
		(row_entries[row.id]).sort(key=lambda x: str(x.heading.name))#, reverse = True)
		#(row_entries[row.id]).sort(key=lambda x: int(x.entry))   - not working

	#The line below converts the dictionary into a list of tuples where tuple is len2 1st item key, item 2 is a list of data entry objects
	sorted_rows = sorted(row_entries.items(), key = lambda x: x[1][order_by_heading].entry, reverse = rev)

	#Logic for deleting a row entry: 
	row_creator_logged_in = []
	for r in sorted_rows:
		row2check = session.query(Row).filter_by(id = r[0]).one()
		row_creator_id = row2check.user_id
		row_creator = session.query(User).filter_by(id = row_creator_id).one()
		if row_creator.user_name == un:
			row_creator_logged_in.append(True)
		else:
			row_creator_logged_in.append(False)


	if request.method == 'POST':
		order_by_heading = int(request.form["heading"][:-1])-1
		rev = int(request.form["heading"][-1:])
		return redirect(url_for('QueryList', list_id = list_id))
	else:
		return render_template('view.html', list = list_to_view, h_items = heading_items, rows = rows, 
								lid = list_id, logged_in=logged_in, 
								un=un, deletable_l = deletable_l, sorted_rows = sorted_rows, 
								row_creator_logged_in = row_creator_logged_in)

@app.route('/select_headings/<int:list_id>', methods = ['GET', 'POST'])
def SelectShortList(list_id):
	list_to_view = session.query(List).filter_by(id = list_id).first()
	heading_items = session.query(HeadingItem).filter_by(list_id = list_to_view.id).order_by(HeadingItem.name.asc())
	if request.method == 'POST':
		heading_ids = request.form.getlist("heading")
		login_session['selected_headings'] = heading_ids
		return redirect(url_for('QueryShortList', list_id = list_id))
	else:
		return render_template('shortlist_choice.html', list = list_to_view, heading_items = heading_items)


@app.route('/<int:list_id>/shortlist', methods = ['GET', 'POST'])
def QueryShortList(list_id):

	global order_by_heading
	global rev


	print "lets check the length of the login session headings selected flwd by each id: ", len(login_session['selected_headings']),\
	[int(e) for e in login_session['selected_headings'] ]
#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	list_to_view = session.query(List).filter_by(id = list_id).first()
	# I can retrieve every heading object in the 'if method == post' section, where they are appended to a list
	rows = session.query(Row).filter_by(list_id = list_to_view.id).order_by(Row.id.asc())
	row_entries = {}

	heading_ids = []
	for i in login_session['selected_headings']:
		heading_ids.append(int(i))
	print heading_ids, "these are the selected heading ids"
	heading_items = []
	heading_items_orig = session.query(HeadingItem).filter_by(list_id = list_to_view.id).order_by(HeadingItem.name.asc())
	for e in heading_items_orig:
		if e.id in heading_ids:
			heading_items.append(e)

	heading_items.sort(key=lambda x: str(x.name))


	#Defining the logic determining creator of item (only person allowed to delete)
	owner_id = list_to_view.user_id
	deletable_l = False # This is val passed to template about wether delete button (for lists) will do what's required or popup saying not allowed 
	# to delete because not creator of ths thing (list, heading, row, entry)
	#print "OWNER IS: ",owner.user_name, "un is: ", un
	owner = session.query(User).filter_by(id = owner_id).one()
	if owner.user_name == un:
		deletable_l = True

	row_entries = {}
	for row in rows:
		row_entries[row.id] = session.query(TextEntry).filter_by(row_id = row.id).order_by(TextEntry.heading_id).all()
		for e in li_of_dtypes[1:]:
			for i in (session.query(e).filter_by(row_id = row.id).all()):
				row_entries[row.id].append(i)

		(row_entries[row.id]).sort(key=lambda x: str(x.heading.name))#, reverse = True)
		#(row_entries[row.id]).sort(key=lambda x: int(x.entry))   - not working



	'''print "reading out all the (k, v) pairs of a list: "
	print row_entries.items()
	print "done with that :) "'''

	orig_sorted_rows = sorted(row_entries.items(), key = lambda x: x[1][order_by_heading].entry, reverse = rev)
	sorted_rows = []
	for i in range(0, len(orig_sorted_rows)):
		sorted_rows.append((orig_sorted_rows[i][0],[]))
		for ele in orig_sorted_rows[i][1]:
			if ele.heading_id in heading_ids:
				sorted_rows[i][1].append(ele)
		sorted_rows[i][1].sort(key=lambda x: str(x.heading.name))
	print "done after"

	sorted_rows.sort(key = lambda x: x[1][order_by_heading].entry, reverse = rev)
	#Logic for deleting a row entry: 
	row_creator_logged_in = []
	for r in sorted_rows:
		row2check = session.query(Row).filter_by(id = r[0]).one()
		row_creator_id = row2check.user_id
		row_creator = session.query(User).filter_by(id = row_creator_id).one()
		if row_creator.user_name == un:
			row_creator_logged_in.append(True)
		else:
			row_creator_logged_in.append(False)



	if request.method == 'POST':
		order_by_heading = int(request.form["heading"][:-1])-1
		rev = int(request.form["heading"][-1:])
		return redirect(url_for('QueryShortList', list_id = list_id))
	else:
		return render_template('view_shortlist.html', list = list_to_view, rows = rows, 
								lid = list_id, logged_in=logged_in, h_items = heading_items,
								un=un, deletable_l = deletable_l, sorted_rows = sorted_rows, 
								row_creator_logged_in = row_creator_logged_in)





@app.route('/<int:list_id>/new_col/', methods = ['GET', 'POST'])
def AddColumn(list_id):

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	list_to_add_to = session.query(List).filter_by(id=list_id).one()
	if request.method == 'POST':
		newhi = HeadingItem(name=request.form['namer'], description=request.form['desc'], entry_data_type = request.form['data_type'], votes=0, lists= list_to_add_to, user=getUser())
		session.add(newhi)
		session.commit()
		flash("Well done! You created a new heading called: {}".format(newhi.name))
		return redirect(url_for('QueryList', list_id = list_id))
	else:
		return render_template('add_column.html', list_id = list_id, lname = list_to_add_to.name, data_types=data_types_tuple, logged_in=logged_in, un=un)
		"""
	kw1 = request.form['kw1']
	if kw1 != None:
		newli.l_keywords.append(ListKeyword(keyword = kw1))
	
	kw2 = request.form['kw2']
	if kw2 != None:
		newli.l_keywords.append(ListKeyword(keyword = kw2))

	kw3 = request.form['kw3']
	if kw3 != None:
		newli.l_keywords.append(ListKeyword(keyword = kw3))"""
	#return "Add a new column (and therefore increase the usefulness of your list{}".format(list_id)

@app.route('/<int:list_id>/heading2edit/', methods = ['GET', 'POST'])
def HeadingList(list_id):

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']


	list_to_edit = session.query(List).filter_by(id = list_id).one()
	heading_items = session.query(HeadingItem).filter_by(list_id = list_id).order_by(HeadingItem.id.asc()).all()
	if request.method == 'POST':
		hid_2_edit = request.form.get('id_of_col')
		return redirect(url_for('EditColumn', list_id = list_id, heading_id = hid_2_edit))
	else:
		return render_template('heading_dropdown.html', list_id = list_id, li = list_to_edit, heading_items = heading_items, 
			logged_in=logged_in, un=un)



@app.route('/<int:list_id>/<int:heading_id>/edit_heading', methods = ['GET', 'POST'])
def EditColumn(list_id, heading_id):
#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	owning_list = session.query(List).filter_by(id = list_id).one()
	heading_2_edit = session.query(HeadingItem).filter_by(id = heading_id).one()
	data_type_dict = {0: "TextEntry", 1: "IntegerEntry", 2: "DateEntry", 3: "TrueFalse",
	 4: "TimeEntry", 5: "Duration", 6: "TwoDecimal", 7: "LargeDecimal"}

	orig_hdng_dtype = heading_2_edit.entry_data_type
	#print "before edit, this is dtype (num, word): ", orig_hdng_dtype, data_type_dict[orig_hdng_dtype]

	#Defining the logic determining creator of item (only person allowed to delete)
	owner = heading_2_edit.user
	deletable_h = False # This is val passed to template about wether delete button (for lists) will do what's required or popup saying not allowed 
	# to delete because not creator of ths thing (list, heading, row, entry)
	#print "OWNER IS: ",owner.user_name, "un is: ", un
	if owner.user_name == un:
		deletable_h = True
	#print deletable_h

	if request.method == 'POST':
		heading_2_edit.name = request.form['namer']
		heading_2_edit.description = request.form['desc']
		#heading_2_edit.entry_data_type = request.form['data_type'] -see paragraph below, cannot edit the data type. 
		#print "New dataType: ", heading_2_edit.entry_data_type
		session.add(heading_2_edit)
		session.commit()

		#Now, if the data type changed, then ALLL the data entries for this type must be remade:
		#Actually, CANNOT do this, as the format of all entries will be different, so make a popup sayin you cannot edit a data type's type 
		"""if heading_2_edit.entry_data_type != orig_hdng_dtype:
			entries_2del_and_replace = session.query(data_type_dict[orig_hdng_dtype]).filter_by(heading_id = heading_id).all()
			for e in entries_2del_and_replace:
				print "e.name: ", e.name
				newhi = HeadingItem(name=e.name, description=e.description, entry_data_type = heading_2_edit.entry_data_type, votes=0, lists= e.lists, user=e.user)
				session.add(newhi)
				session.commit()

				session.delete(e)
				session.commit()"""


		flash("Damn Son! You just edited the heading: {}".format(heading_2_edit.name))

		return redirect(url_for('QueryList', list_id = list_id))
	else:
		return render_template('edit_column.html', list_id = list_id, heading = heading_2_edit, list_name = owning_list.name, 
			data_type_dict=data_type_dict, logged_in=logged_in, un=un, deletable_h = deletable_h)




@app.route('/<int:list_id>/<int:col_id>/delete_col/', methods = ['GET', 'POST'])
def DeleteColumn(list_id, col_id):

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	list2del_col_4rm = session.query(List).filter_by(id = list_id).one()
	column2del = session.query(HeadingItem).filter_by(id = col_id).one()

	if request.method == 'POST':
#Get all of the actual entries related to this column
		for e in li_of_dtypes:
			e_2_del = session.query(e).filter_by(heading_id = col_id).all()
			if len(e_2_del) > 0:
				for w in e_2_del:
					session.delete(w)
					session.commit()

		#Now, delete the actual heading:
		session.delete(column2del)
		session.commit()
		flash("Damn Son! You just deleted the heading: {}".format(column2del.name))
		return redirect(url_for('QueryList', list_id=list_id))
	else:
		return render_template('delete_column.html', li = list2del_col_4rm, 
			col = column2del, logged_in=logged_in, un=un)

@app.route('/<int:list_id>/new_row/', methods = ['GET', 'POST'])
def AddRow(list_id):

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	#List of tuples of data types

	list_to_add_to = session.query(List).filter_by(id=list_id).one()
	heading_items = session.query(HeadingItem).filter_by(list_id = list_id).order_by(HeadingItem.id.asc()).all()
	if request.method == 'POST':
		new_row = Row(votes = 0, lists = list_to_add_to, user = getUser())
		session.add(new_row)
		session.commit()
		for i in range(0, len(heading_items)):
			form_val = request.form["name_{}".format(i)]
			stri = data_types[heading_items[i].entry_data_type]
			if str(stri)[-11:-2] == "DateEntry":
				if len(form_val) < 1 or str(form_val)[4] != "-" or form_val== '':
					form_val = datetime.strptime('0001-01-01' , '%Y-%m-%d')
			elif str(stri)[-11:-2] == "egerEntry":
				if form_val == '' or form_val == ' ' or type(int(form_val)) != int:
					form_val = 0
				else:
					form_val = int(form_val)
			elif str(stri)[-11:-2] == "woDecimal" or str(stri)[-11:-2] == "geDecimal":
				if form_val == '' or form_val == ' ' or type(float(form_val)) != float:
					form_val = 0.00
				else:
					form_val = float(form_val)
			elif str(stri)[-11:-2] == "TextEntry":
				if type(form_val) != str:				
					form_val = str(form_val)
			elif str(stri)[-11:-2] == "TrueFalse":
				form_val = bool(form_val)

			e1 = stri(entry=form_val, votes=0, heading = heading_items[i] , lists =new_row, user = getUser())
			session.add(e1)
			session.commit()

		flash("Well done! You created a new row with ID: {}.".format(new_row.id))
		return redirect(url_for('QueryList', list_id = list_id))
	else:
		return render_template('add_row.html', list_id = list_id, h_items = heading_items, dt_tr = li_of_dtypes_str,
			list = list_to_add_to, logged_in=logged_in, un=un)
	#return "Add a new row to your list. That is, a new entry (and therefore increase the usefulness of your list with id: {}). ".format(list_id)

@app.route('/<int:list_id>/<int:row_id>/edit_row/', methods = ['GET', 'POST'])
def EditRow(list_id, row_id):

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	li_2_edit = session.query(List).filter_by(id = list_id).one()
	row_2_edit = session.query(Row).filter_by(id = row_id).one()
	headings = session.query(HeadingItem).filter_by(list_id = list_id).order_by(HeadingItem.id.asc()).all()

	entries = []
	for e in li_of_dtypes:
		group_of_entries = session.query(e).filter_by(row_id = row_id).all()
		if len(group_of_entries) > 0:
			for w in group_of_entries:
				entries.append((w.heading_id, w))

	entries = [b for a,b in sorted((tup[0], tup) for tup in entries)]
	if request.method == 'POST':
		for i in range(0, len(headings)):
			if i < len(entries):
				namer = str(headings[i].name)
				entries[i][1].entry = request.form["h_{}".format(namer)]
				dtype_A = data_types[headings[i].entry_data_type]
				if str(dtype_A)[-11:-2] == "egerEntry":
					if entries[i][1].entry == '' or entries[i][1].entry == ' ' or type(int(float(entries[i][1].entry))) != int:
						entries[i][1].entry = 0
					else:
						entries[i][1].entry = int(float(entries[i][1].entry))
				elif str(dtype_A)[-11:-2] == "woDecimal" or str(dtype_A)[-11:-2] == "geDecimal":
					if entries[i][1].entry == '' or entries[i][1].entry == ' ':
						entries[i][1].entry = 0.00

				elif str(dtype_A)[-11:-2] == "TrueFalse":
					if str(entries[i][1].entry) == 'False':
						entries[i][1].entry = False
					else:
						entries[i][1].entry = bool(entries[i][1].entry)
				session.add(entries[i][1])
				session.commit()
			else:
				type_of_entry = str(data_types[headings[i].entry_data_type])
				form_val = request.form['{}'.format(headings[i].name)]
				if type_of_entry[-11:-2] == "DateEntry":
					if len(form_val) < 1 or str(form_val)[4] != "-" or form_val== '':
						form_val = datetime.strptime('0001-01-01' , '%Y-%m-%d')
				elif type_of_entry[-11:-2] == "egerEntry":
					if form_val == '' or form_val == ' ' or type(int(float(form_val))) != int:
						form_val = 0
				elif type_of_entry[-11:-2] == "woDecimal" or type_of_entry[-11:-2] == "geDecimal":
					if form_val == '' or form_val == ' ' or type(float(form_val)) != float:
						form_val = 0.00
					else:
						form_val = float(form_val)
				elif type_of_entry[-11:-2] == "TextEntry":
					if type(form_val) != str:
						form_val = str(form_val)
				elif type_of_entry[-11:-2] == "TrueFalse":
					form_val = bool(form_val)
				e_type = li_of_dtypes[headings[i].entry_data_type] #This section is for entries that are blank but there is a heading for them... 
				new_ent = e_type(entry = form_val,votes=0, heading = headings[i] , lists =row_2_edit)
				session.add(new_ent)
				session.commit()

		flash("Well done! You just made some edits to the row with ID: {}".format(row_2_edit.id))
		return redirect(url_for('QueryList', list_id = list_id))
	else:
		return render_template('edit_row.html', li_2_edit = li_2_edit, headings = headings, row_2_edit = row_2_edit, 
			entries = entries, logged_in=logged_in, un=un)


@app.route('/<int:list_id>/<int:row_id>/delete_row/', methods = ['GET', 'POST'])
def DeleteRow(list_id, row_id):

#Logged in logic and rules (permissions, etc)
	logged_in = False
	un = ''
	if 'username' in login_session:
		logged_in = True
		un = login_session['username']

	list2del_col_4rm = session.query(List).filter_by(id = list_id).one()
	row_2_del = session.query(Row).filter_by(id = row_id).one()

	#Defining the logic determining creator of item (only person allowed to delete)
	owner = row_2_del.user
	deletable_r = False # This is val passed to template about wether delete button (for lists) will do what's required or popup saying not allowed 
	# to delete because not creator of ths thing (list, heading, row, entry)
	#print "OWNER IS: ",owner.user_name, "un is: ", un
	if owner.user_name == un:
		deletable_r = True
	#print deletable_r


	entries_2_del = []
	for i in li_of_dtypes:
		entry = session.query(i).filter_by(row_id = row_id).all()
		for e in entry:
			entries_2_del.append(e)

	if request.method == 'POST':
		for e in entries_2_del:
			session.delete(e)
			session.commit()

		session.delete(row_2_del)
		session.commit()
		flash("Damn Son! You just deleted the row with ID: {}. Alas it is no more!".format(row_2_del.id))
		return redirect(url_for('QueryList', list_id = list_id))
	else:
		return render_template('delete_row.html', lname = list2del_col_4rm.name, 
			num_entries = len(entries_2_del), list_id = list_id, row_id = row_id, logged_in=logged_in, un=un, deletable_r=deletable_r)


	return "Delete this row for list number: {}, row id: {}".format(list_id, row_id)




#____LIST COMMENTS______

@app.route('/<int:list_id>/new_comment/')
def NewListComment(list_id):
	return render_template('new_comment.html', list_id = list_id)
	#return "Page for making a new comment for the list: {}.".format(list_id)

@app.route('/<int:list_id>/comments/')
def ListComments(list_id):
	return "A list of all the comments for the list: {}.\n \
	There should be: VIEW|COMMENT|EDIT|DELETE buttons for each of the entries".format(list_id)

#@app.route('/<int:list_id>/<int:comment_id>/')
@app.route('/<int:list_id>/<int:comment_id>/view_list_comment/')
def ViewListComment(list_id,comment_id):
	return "View a single comment with buttons on here for when you want to edit and or delete this comment from list id:{}, comment id:{}".format(list_id, comment_id)

@app.route('/<int:list_id>/<int:comment_id>/edit_list_comment')
def EditListComment(list_id,comment_id):
	return "Page for editing a comment for the list: list{}, comment:{}".format(list_id, comment_id)

@app.route('/<int:list_id>/<int:comment_id>/delete_list_comment')
def DeleteListComment(list_id,comment_id):
	return "Page for deleting a comment for the list: list{}, comment:{}".format(list_id, comment_id)


#____HEADING COMMENTS______

@app.route('/<int:col_id>/new_comment/')
def NewColumnComment(col_id):
	return "Page for making a new comment for the col: {}.".format(col_id)

@app.route('/<int:col_id>/comments/')
def ColumnComments(col_id):
	return "A list of all the comments for the col: {}.\n \
	There should be: VIEW|COMMENT|EDIT|DELETE buttons for each of the entries".format(col_id)

#@app.route('/<int:col_id>/<int:comment_id>/')
@app.route('/<int:col_id>/<int:comment_id>/view_col_comment/')
def ViewColumnComment(col_id,comment_id):
	return "View a single comment with buttons on here for when you want to edit and or delete this comment from col id:{}, comment id:{}".format(col_id, comment_id)

@app.route('/<int:col_id>/<int:comment_id>/edit_col_comment')
def EditColumnComment(col_id,comment_id):
	return "Page for editing a comment for the col: col{}, comment:{}".format(col_id, comment_id)

@app.route('/<int:col_id>/<int:comment_id>/delete_col_comment')
def DeleteColumnComment(col_id,comment_id):
	return "Page for deleting a comment for the col: col{}, comment:{}".format(col_id, comment_id)



#____ROW COMMENTS______

@app.route('/<int:row_id>/new_comment/')
def NewRowComment(row_id):
	return "Page for making a new comment for the row: {}.".format(row_id)

@app.route('/<int:row_id>/comments/')
def RowComments(row_id):
	return "A list of all the comments for the row with VIEW|COMMENT|EDIT|DELETE buttons for each of the comments for this row with id: {}.".format(row_id)

#@app.route('/<int:row_id>/<int:comment_id>/')
@app.route('/<int:row_id>/<int:comment_id>/view_row_comment/')
def ViewRowComment(row_id,comment_id):
	return "View a single comment with buttons on here for when you want to edit and or delete this comment from row id:{}, comment id:{}".format(row_id, comment_id)

@app.route('/<int:row_id>/<int:comment_id>/edit_row_comment')
def EditRowComment(row_id,comment_id):
	return "Page for editing a comment for the row: row{}, comment:{}".format(row_id, comment_id)

@app.route('/<int:row_id>/<int:comment_id>/delete_row_comment')
def DeleteRowComment(row_id,comment_id):
	return "Page for deleting a comment for the row: row{}, comment:{}".format(row_id, comment_id)


#____ITEM COMMENTS______

@app.route('/<int:row_id>/<int:col_id>/new_comment/')
def NewItemComment(row_id, col_id):
	return "Page for making a new comment for the item: Row{}, Col{}.".format(row_id, col_id)

@app.route('/<int:row_id>/<int:col_id>/comments/')
def ItemComments(row_id, col_id):
	return "A list of all the comments for the item with VIEW|COMMENT|EDIT|DELETE buttons for each of the comments for this item: row{}, col{}".format(row_id, col_id)

#@app.route('/<int:row_id>/<int:col_id>/<int:comment_id>/')
@app.route('/<int:row_id>/<int:col_id>/<int:comment_id>/view_row_comment/')
def ViewItemComment(row_id,col_id, comment_id):
	return "View a single comment with buttons on here for when you want to edit and or delete this comment from row id:{}, col_id: {} comment id:{}".format(row_id, col_id, comment_id)

@app.route('/<int:row_id>/<int:col_id>/<int:comment_id>/edit_row_comment')
def EditItemComment(row_id,col_id,comment_id):
	return "Page for editing a comment for the row: row{}, col_id{}, comment id:{}".format(row_id, col_id, comment_id)

@app.route('/<int:row_id>/<int:col_id>/<int:comment_id>/delete_row_comment')
def DeleteItemComment(row_id, col_id, comment_id):
	return "Page for deleting a comment for the row: row{}, col_id{}, comment id:{}".format(row_id, col_id, comment_id)

#Creating Users
def createUser(login_session):
	newUser = User(user_name = login_session['username'], email = login_session['email'], picture = login_session['picture'])
	session.add(newUser)
	session.commit()
	user = session.query(User).filter_by(email = login_session['email']).one()
	return user.id 

def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

def getUser():
	"""Use this method when declaring a new list, row, heading, entry"""
	try:
		user = session.query(User).filter_by(email = login_session['email']).one()
		return user
	except:
		return None

# Make a page to add additional info on the user - like a description, first name, last name, age, etc....
#____COMMENT COMMENTS______ - I don't think this is necessary? 

if __name__ == '__main__':
	app.secret_key = 'super_secret_key'
	app.debug = True
	app.run(host = '0.0.0.0', port = 5000)





#Redundant - for deleting lists:
'''
		for row in rows_2_del:
			e_2_del1 = session.query(TextEntry).filter_by(row_id = row.id).all()
			if len(e_2_del1) > 0:
				for w in e_2_del1:
					session.delete(w)
					session.commit()

			e_2_del2 = session.query(IntegerEntry).filter_by(row_id = row.id).all()
			if len(e_2_del2) > 0:
				for w in e_2_del2:
					session.delete(w)
					session.commit()

			e_2_del3 = session.query(DateEntry).filter_by(row_id = row.id).all()
			if len(e_2_del3) > 0:
				for w in e_2_del3:
					session.delete(w)
					session.commit()

			e_2_del4 = session.query(TrueFalse).filter_by(row_id = row.id).all()
			if len(e_2_del4) > 0:
				for w in e_2_del4:
					session.delete(w)
					session.commit()

			e_2_del5 = session.query(TimeEntry).filter_by(row_id = row.id).all()
			if len(e_2_del5) > 0:
				for w in e_2_del5:
					session.delete(w)
					session.commit()

			e_2_del6 = session.query(Duration).filter_by(row_id = row.id).all()
			if len(e_2_del6) > 0:
				for w in e_2_del6:
					session.delete(w)
					session.commit()

			e_2_del7 = session.query(TwoDecimal).filter_by(row_id = row.id).all()
			if len(e_2_del7) > 0:
				for w in e_2_del7:
					session.delete(w)
					session.commit()

			e_2_del8 = session.query(LargeDecimal).filter_by(row_id = row.id).all()
			if len(e_2_del8) > 0:
				for w in e_2_del8:
					session.delete(w)
					session.commit()

			e_2_del9 = session.query(DateTimeEntry).filter_by(row_id = row.id).all()
			if len(e_2_del9) > 0:
				for w in e_2_del9:
					session.delete(w)
					session.commit()
'''
			#Lastly, delete every row


'''
Also Redundants - This is how each of the entries was added to each row for the display of a list (QueryList): 
	# Need to collect data entries for each of the different types of entries that are available
	for row in rows:
		row_entries[row.id] = session.query(TextEntry).filter_by(row_id = row.id).order_by(TextEntry.heading_id).all()
		for i in (session.query(IntegerEntry).filter_by(row_id = row.id).all()):
			row_entries[row.id].append(i)
		for i in (session.query(DateEntry).filter_by(row_id = row.id).all()):
			row_entries[row.id].append(i)
		for i in (session.query(DateTimeEntry).filter_by(row_id = row.id).all()):
				row_entries[row.id].append(i)
		for i in (session.query(TrueFalse).filter_by(row_id = row.id).all()):
				row_entries[row.id].append(i)
		for i in (session.query(TimeEntry).filter_by(row_id = row.id).all()):
				row_entries[row.id].append(i)
		for i in (session.query(Duration).filter_by(row_id = row.id).all()):
				row_entries[row.id].append(i)
		for i in (session.query(TwoDecimal).filter_by(row_id = row.id).all()):
				row_entries[row.id].append(i)
		for i in (session.query(LargeDecimal).filter_by(row_id = row.id).all()):
				row_entries[row.id].append(i)'''