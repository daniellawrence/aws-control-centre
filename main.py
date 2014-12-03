#!/usr/bin/env python
from flask import Flask
from functools import wraps
from flask import request, Response, session, redirect, url_for, \
    render_template
from boto import ec2


app = Flask(__name__)
app.region_name = 'ap-southeast-2'


def connect_to_region():
    aws_connection = ec2.connect_to_region(
        region_name=app.region_name,
        aws_access_key_id=session['username'],
        aws_secret_access_key=session['password'],
        is_secure=True,
        validate_certs=False
    )
    return aws_connection


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    session.pop('username', None)
    session.pop('password', None)
    session['username'] = username
    session['password'] = password
    aws_connection = connect_to_region()
    number_of_tags = len(aws_connection.get_all_tags())

    if number_of_tags > 0:
        return True
    return False


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
    del session['username']
    del session['password']
    request.authorization = None
    session.pop('username', None)
    session.pop('password', None)
    return authenticate()
    return redirect(url_for('index'))


@app.route("/instance")
@requires_auth
def instances():
    aws_connection = connect_to_region()
    instance_list = aws_connection.get_all_instances()
    return render_template(
        'index.html',
        instance_list=instance_list, username=session['username']
    )


@app.route("/instance/<instance_id>/<action>")
@requires_auth
def instances_action(instance_id, action):
    aws_connection = connect_to_region()
    instance = aws_connection.get_all_instances(
        instance_ids=[instance_id]
    )[0].instances[0]
    print(dir(instance))
    return render_template(
        'instance_action.html',
        instance=instance,
        action=action,
        instance_id=instance_id
    )


@app.route("/")
@requires_auth
def index():
    return redirect(url_for('instances'))


def validate_tags(user_tags, machine_tags):
    REQUIRED_MATCHES = len(user_tags.keys())
    TAG_MATCHES = 0
    for mtag, mval in machine_tags.items():
        if mtag in user_tags:
            uval = user_tags[mtag]
            if isinstance(uval, str):
                uval = [uval]
            if mval in uval:
                TAG_MATCHES += 1

    if TAG_MATCHES == REQUIRED_MATCHES:
        return True
    return False

if __name__ == "__main__":
    app.debug = True
    app.host = '0.0.0.0'
    app.secret_key = 'testytesttestx'
    app.run()
