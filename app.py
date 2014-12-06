#!/usr/bin/env python
from flask import Flask, flash
from functools import wraps
from flask import request, Response, session, redirect, url_for, \
    render_template
from boto import ec2, iam
from collections import defaultdict

from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.superadmin import Admin
from flask.ext.superadmin.model.base import ModelAdmin
from flask.ext import superadmin

app = Flask(__name__)
app.region_name = 'ap-southeast-2'


# Create in-memory database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.sqlite'
app.config['SQLALCHEMY_ECHO'] = True
db = SQLAlchemy(app)

# Create M2M table
user_tags_table = db.Table(
    'user_tags', db.Model.metadata,
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'))
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    tags = db.relationship('Tag', secondary=user_tags_table)

    # Required for administrative interface
    def __unicode__(self):
        return self.username


class Tag(db.Model):
    id = db.Column(db.Integer, unique=True, primary_key=True)
    name = db.Column(db.Unicode(255))
    value = db.Column(db.Unicode(255))
    __tablename__ = 'tag'
    __table_args__ = (db.UniqueConstraint('name', 'value'), {})

    def __unicode__(self):
        return "%s=%s" % (self.name, self.value)


def memorize(function):
    memo = {}

    def wrapper(*args):
        key = "%s%s" % (function.__name__, args)
        if key in memo:
            return memo[key]
        else:
            rv = function(*args)
            memo[key] = rv
        return rv
    return wrapper


def connect_to_region():
    aws_connection = ec2.connect_to_region(
        region_name=app.region_name,
        aws_access_key_id=session['username'],
        aws_secret_access_key=session['password'],
        is_secure=True,
        validate_certs=False
    )
    iam_connection = iam.connect_to_region(
        region_name=app.region_name,
        aws_access_key_id=session['username'],
        aws_secret_access_key=session['password'],
        is_secure=True,
        validate_certs=False
    )
    user_data = iam_connection.get_user()['get_user_response']['get_user_result']['user']
    session.update(user_data)
    return aws_connection


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    session.pop('username', None)
    session.pop('password', None)
    session['username'] = username
    session['password'] = password
    # Test if we can connect to a region
    connect_to_region()
    return True


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


@app.route("/logoff/")
def logoff():
    for session_key in ('username', 'password'):
        if session_key in session:
            del session[session_key]
            session.pop(session_key, None)
    session.clear()
    request.authorization = None
    return authenticate()
    return redirect(url_for('index'))


@memorize
def get_all_instances():
    instance_list = []
    aws_connection = connect_to_region()
    raw_instance_list = aws_connection.get_all_instances()
    for r in raw_instance_list:
        i = r.instances[0]
        if 'Environment' not in i.tags:
            print("Skipping %s missing Environment" % i)
            continue
        if 'AppName' not in i.tags:
            print("Skipping %s missing AppName" % i)
            continue
        if 'CostCentre' not in i.tags:
            print("Skipping %s missing CostCentre" % i)
            continue

        # We only want to start machines, not stop them
        # if i.state in ('running',):
        #    continue
        instance_list.append(i)
    instance_list.sort(key=lambda x: "%s-%s-%s" % (
        x.tags['AppName'], x.tags['Environment'], x.tags['CostCentre']
    ))
    return instance_list


@memorize
def get_single_instance(instance_id):
    aws_connection = connect_to_region()
    instance = aws_connection.get_all_instances(
        instance_ids=[instance_id]
    )[0].instances[0]
    return instance


def get_user_tags():
    user_name = session['user_name']
    my_user_tags = defaultdict(list)
    user = User.query.filter_by(username=user_name).first()
    if user is None:
        return None
    for t in user.tags:
        my_user_tags[t.name].append(t.value)
    print(type(my_user_tags))
    return my_user_tags


@app.route("/instance/")
@requires_auth
def instances():
    my_user_tags = get_user_tags()
    if my_user_tags is None:
        return redirect('/admin/user')
    instance_list = get_all_instances()
    instance_list = filter_resources_by_tag(
        instance_list,
        my_user_tags
    )
    return render_template(
        'instance_list.html',
        instance_list=instance_list,
        username=session['username'],
        my_user_tags=my_user_tags,
    )


@app.route("/instance/<instance_id>/<action>", methods=['GET', 'POST'])
@requires_auth
def instances_action(instance_id, action):
    instance = get_single_instance(instance_id)
    my_user_tags = get_user_tags()
    # Take action
    if request.method == 'POST':
        instance = filter_resources_by_tag(
            [instance],
            my_user_tags
        )[0]
        print "Would have shutdown %s" % instance.id

    return render_template(
        'instance_action.html',
        instance=instance,
        action=action,
        instance_id=instance_id
    )


@app.route("/")
def index():
    return render_template(
        'index.html',
    )


def filter_resources_by_tag(resource_list, user_tags):
    filtered_resource_list = []
    for r in resource_list:
        if validate_tags(user_tags, r.tags):
            filtered_resource_list.append(r)
    return filtered_resource_list


def validate_tags(user_tags, machine_tags):
    REQUIRED_MATCHES = len(user_tags.keys())
    TAG_MATCHES = 0
    for mtag, mval in machine_tags.items():
        if mtag in user_tags:
            uval = user_tags[mtag]
            if isinstance(uval, str):
                uval = [uval]
            print("%s(%s) in %s, %s" % (mtag, mval, uval, mval in uval))
            if mval in uval:
                TAG_MATCHES += 1

    if TAG_MATCHES == REQUIRED_MATCHES:
        return True
    return False


@requires_auth
@app.route("/refresh/users")
def refresh_users():
    iam_connection = iam.connect_to_region(
        region_name=app.region_name,
        aws_access_key_id=session['username'],
        aws_secret_access_key=session['password'],
        is_secure=True,
        validate_certs=False
    )
    add_users = 0
    all_users = iam_connection.get_all_users()
    for user in all_users['list_users_response']['list_users_result']['users']:
        u = User(username=user['user_name'])
        try:
            db.session.add(u)
            db.session.commit()
        except Exception:
            continue
        add_users += 1
    flash("Added %d users from AWS" % add_users)
    return redirect("/admin/user/")


@requires_auth
@app.route("/refresh/tags/")
def refresh_tags():
    tags = []
    added_tags = 0

    for instance in get_all_instances():
        for tag_name, tag_value in instance.tags.items():
            t = Tag(name=tag_name, value=tag_value)
            key = "%s=%s" % (tag_name, tag_value)
            if key in tags:
                continue
            try:
                db.session.add(t)
                tags.append(key)
                db.session.commit()
                added_tags += 1
            except Exception:
                continue
    flash("Added %d tags from AWS" % added_tags)

    return redirect("/admin/tag/")


class RefreshTags(superadmin.BaseView):

    @superadmin.expose('/')
    def index(self):
        return refresh_tags()


class RefreshUsers(superadmin.BaseView):

    @superadmin.expose('/')
    def index(self):
        return refresh_users()


class UserAdmin(ModelAdmin):
    list_display = ('username',)
    search_fields = list_display


class TagAdmin(ModelAdmin):
    list_display = ('name', 'value', )
    search_fields = list_display

if __name__ == "__main__":
    app.debug = True
    app.host = '0.0.0.0'
    app.secret_key = 'testytesttestxx'

    admin = Admin(app, 'AWS CC')
    # Add views
    admin.register(User, UserAdmin, session=db.session)
    admin.register(Tag, TagAdmin, session=db.session)
    admin.add_view(RefreshTags(category='Refresh from AWS'))
    admin.add_view(RefreshUsers(category='Refresh from AWS'))

    db.create_all()

    app.run()
