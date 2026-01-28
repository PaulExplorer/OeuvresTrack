from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    session,
    send_from_directory,
    redirect,
    make_response,
    abort,
)

from flask_minify import Minify
# from flask_compress import Compress
from flask_caching import Cache
from flask_talisman import Talisman

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


from api import (
    search_new_book,
    search_new_movie,
    search_new_tv,
    get_new_element,
    get_user_ulist,
    add_ulist,
    get_ucatalog,
    update_ucatalog,
    remove_ulist,
    toggle_giveup,
    set_rank,
    get_tierlist,
    set_settings,
    update_user,
    update_password,
    set_lexicon,
    get_lexicon,
    get_settings,
    hard_reload,
    save_subscription_to_db,
    default_lexicon,
)
from datetime import timedelta
from modals import User
from functools import wraps

import os

if os.getenv("ENV") != "production":
    print("Development environment")
    from dotenv import load_dotenv

    load_dotenv()


VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")

debug = True
testing = False

if os.getenv("ENV") == "production":
    debug = False


def get_cache_key(request):
    return request.url


def get_user_id_key(*args, **kwargs):
    if "user" in session:
        return f"{request.url}-{session['user']['id']}"
    return request.url


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=90)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60 * 60 * 24 * 7

if not debug and not testing:
    cache = Cache(
        app,
        config={
            "DEBUG": debug,
            "CACHE_TYPE": "SimpleCache",
            "CACHE_DEFAULT_TIMEOUT": 60 * 60,
        },
    )
else:
    cache = Cache(app, config={"CACHE_TYPE": "NullCache"})

# compress = Compress()
# compress.init_app(app)

Minify(app=app, html=True, js=True, cssless=True)

csp = {
    "default-src": [
        "'self'",
    ],
    "script-src": [
        "'self'",
        "'unsafe-inline'",
        "https://storage.googleapis.com",
        "https://cdn.jsdelivr.net",
    ],
    "style-src": [
        "'self'",
        "'unsafe-inline'",
        "https://fonts.googleapis.com",
    ],
    "font-src": [
        "'self'",
        "https://fonts.gstatic.com",
    ],
    "img-src": [
        "'self'",
        "https://image.tmdb.org",
        "https://*.booknode.com",
        "data:",
    ],
    "connect-src": [
        "'self'",
        "https://fonts.googleapis.com",
        "https://fonts.gstatic.com",
        "https://image.tmdb.org",
        "https://*.booknode.com",
        "https://cdn.jsdelivr.net"
    ],
    "manifest-src": [
        "'self'",
    ],
}


Talisman(app, content_security_policy=csp, force_https=False)

if not debug:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["300 per day", "100 per hour"],
        storage_uri=os.getenv("MONGODB_URI"),
        strategy="fixed-window",
    )
else:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["3000 per day", "800 per hour"],
        storage_uri=os.getenv("MONGODB_URI"),
        strategy="fixed-window",
    )

# if not debug and not testing and False:
#    compress.cache = cache
#    compress.cache_key = get_cache_key


@app.before_request
def make_session_permanent():
    session.permanent = True


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "logged_in" in session:
            return f(*args, **kwargs)
        else:
            return redirect("/?action=login")

    return wrap


def conditional_decorator(dec, condition):
    def decorator(func):
        if not condition:
            return func
        return dec(func)

    return decorator


def no_cache(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"

        cache.delete(get_cache_key(request))

        return response

    return decorated_function


@app.route("/app/", methods=["GET", "POST"])
@login_required
@conditional_decorator(
    cache.cached(timeout=60 * 60, make_cache_key=get_user_id_key), not debug
)
def app_home():
    return render_template(
        "home.html",
        setting=False,
        tierlist=False,
        modalAdd=False,
        modalEdit=False,
        modalEditData={"id": "", "type": ""},
        url="/app/",
    )


@app.route("/app/settings", methods=["GET", "POST"])
@login_required
@conditional_decorator(
    cache.cached(timeout=60 * 60, make_cache_key=get_user_id_key), not debug
)
def app_settings():
    return render_template(
        "home.html",
        setting=True,
        tierlist=False,
        modalAdd=False,
        modalEdit=False,
        modalEditData={"id": "", "type": ""},
        url="/app/settings",
    )


@app.route("/app/tierlist", methods=["GET", "POST"])
@login_required
@conditional_decorator(
    cache.cached(timeout=60 * 60, make_cache_key=get_user_id_key), not debug
)
def app_tierlist():
    return render_template(
        "home.html",
        setting=False,
        tierlist=True,
        modalAdd=False,
        modalEdit=False,
        modalEditData={"id": "", "type": ""},
        url="/app/tierlist",
    )


@app.route("/app/<type>/<id>/", methods=["GET", "POST"])
@login_required
@conditional_decorator(
    cache.cached(timeout=60 * 60, make_cache_key=get_user_id_key), not debug
)
def app_edit(id, type):
    return render_template(
        "home.html",
        setting=False,
        tierlist=False,
        modalAdd=False,
        modalEdit=True,
        modalEditData={"id": id, "type": type},
        url=f"/app/{id}/{type}",
    )


@app.route("/app/add", methods=["GET", "POST"])
@login_required
@conditional_decorator(
    cache.cached(timeout=60 * 60, make_cache_key=get_user_id_key), not debug
)
def app_add():
    return render_template(
        "home.html",
        setting=False,
        tierlist=False,
        modalAdd=True,
        modalEdit=False,
        modalEditData={"id": "", "type": ""},
        url="/app/add",
    )


@app.route("/", methods=["GET", "POST"])
@no_cache
def index():
    if session.get("logged_in") == True:
        return redirect("/app")
    if request.method == "POST" and "action" in request.args:
        if request.args["action"] == "login":
            return User().login()
        elif request.args["action"] == "register":
            return User().signup()
    return render_template("index.html")


@app.route("/logout")
@login_required
def logout():
    return User().signout()


@app.route("/subscribe", methods=["POST"])
@login_required
@no_cache
def subscribe():
    subscription_data = request.get_json()

    user_id = session["user"]["id"]
    save_subscription_to_db(user_id, subscription_data)

    return jsonify({"status": "success"}), 201


@app.route("/api/new/<type>/<query>", methods=["GET"])
@login_required
@conditional_decorator(
    cache.cached(timeout=60 * 20, make_cache_key=get_user_id_key), not debug
)
def api_new_query(type: str, query: str):
    if query is not None and len(query) < 1:
        abort(400)

    if type == "movie":
        return search_new_movie(query, user_id=session["user"]["id"])
    elif type == "tv":
        return search_new_tv(query, user_id=session["user"]["id"])
    elif type == "book":
        return search_new_book(query)
    abort(400)


@app.route("/api/get/<type>/<id>", methods=["GET"])
@login_required
@conditional_decorator(cache.cached(timeout=60 * 60), not debug)
def api_get(type: str, id: str):
    if ["movie", "tv", "book", "books"].count(type) == 0:
        abort(400)

    new_element = get_new_element(type, id)
    if new_element:
        return new_element
    abort(404)


@app.route("/api/user", methods=["POST"])
@login_required
@no_cache
def api_user():
    if "name" not in request.json and "email" not in request.json:
        abort(400)

    result = update_user(session["user"]["id"], request.json)
    if result["status"] == "success":
        if "name" in request.json:
            session["user"]["name"] = request.json["name"]
        if "email" in request.json:
            session["user"]["email"] = request.json["email"]
    return result


def validate_lexicon(lexicon):
    for entry in default_lexicon.keys():
        if entry not in lexicon:
            return False

        for field in default_lexicon[entry]:
            if "text" not in field or "position" not in field:
                return False
    return True


@app.route("/api/lexicon", methods=["GET", "POST"])
@login_required
@no_cache
def api_lexicon():
    if request.method == "POST":
        if not validate_lexicon(request.json):
            abort(400)
        return set_lexicon(session["user"]["id"], request.json)
    return get_lexicon(session["user"]["id"])


@app.route("/api/user/password", methods=["POST"])
@login_required
@no_cache
def api_user_password():
    if (
        "oldPassword" not in request.json
        or "newPassword" not in request.json
        or "confirmPassword" not in request.json
    ):
        abort(400)
    return update_password(session["user"]["id"], request.json)


@app.route("/api/user/list", methods=["GET"])
@no_cache
@limiter.limit("10 per minute; 150 per hour; 300 per day")
def get_user_list():
    if "user" not in session:
        return jsonify({"status": "error"}), 401
    return get_user_ulist(session["user"]["id"])


@app.route("/api/user/list/hard", methods=["GET"])
@login_required
@no_cache
@limiter.limit("10 per minute; 30 per hour; 50 per day")
def hard_reload_endpoint():
    return hard_reload(session["user"]["id"])


@app.route("/api/user/add/<type>/<id>", methods=["GET"])
@login_required
@no_cache
@limiter.limit("10 per minute; 150 per hour; 300 per day")
def add_user_list(type: str, id: str):
    if ["movie", "tv", "book", "books"].count(type) == 0:
        abort(400)
    result = add_ulist(session["user"]["id"], type, id)
    if result is not None:
        return jsonify({"status": "success", "data": result}), 201
    return jsonify({"status": "error"}), 400


@app.route("/api/user/delete/<type>/<id>", methods=["GET"])
@login_required
@no_cache
def delete_user_list(type: str, id: str):
    if ["movie", "tv", "book", "books"].count(type) == 0:
        abort(400)
    if remove_ulist(session["user"]["id"], type, id):
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400


@app.route("/api/user/update/<type>/<id>", methods=["POST"])
@login_required
@no_cache
@limiter.limit("20 per minute; 200 per hour; 400 per day")
def update_user_list(type: str, id: str):
    if ["movie", "tv", "book", "books"].count(type) == 0:
        abort(400)

    if "season_number" in request.json and "changes" in request.json:
        result = update_ucatalog(
            user_id=session["user"]["id"],
            type=type,
            id=id,
            season_number=request.json["season_number"],
            changes=request.json["changes"],
        )
        if result is not None:
            return jsonify({"status": "success", "data": result}), 200
    return jsonify({"status": "error"}), 400


@app.route("/api/user/get/<type>/<id>", methods=["GET"])
@login_required
@no_cache
@limiter.limit("20 per minute; 200 per hour; 400 per day")
def get_user_content(type: str, id: str):
    if ["movie", "tv", "book", "books"].count(type) == 0:
        abort(400)
    return get_ucatalog(type=type, id=id, user_id=session["user"]["id"])


@app.route("/api/user/giveup/<type>/<id>", methods=["GET"])
@login_required
@no_cache
def togle_content_giveup(type, id):
    if ["movie", "tv", "book", "books"].count(type) == 0:
        abort(400)
    result = toggle_giveup(user_id=session["user"]["id"], type=type, id=id)
    if result is not None:
        return jsonify({"status": "success", "data": result}), 200
    return jsonify({"status": "error"}), 400


@app.route("/api/user/rank/<type>/<id>", methods=["POST"])
@login_required
@no_cache
@limiter.limit("20 per minute; 200 per hour; 400 per day")
def set_content_rank(type, id):
    if ["movie", "tv", "book", "books"].count(type) == 0:
        abort(400)
    result = set_rank(
        user_id=session["user"]["id"],
        type=type,
        id=id,
        rank=request.json["rank"],
    )
    if result is not None:
        return jsonify({"status": "success", "data": result}), 200
    return jsonify({"status": "error"}), 400


@app.route("/api/tierlist", methods=["GET"])
@login_required
@no_cache
def tierlist_endpoint():
    return get_tierlist(session["user"]["id"])


@app.route("/api/settings", methods=["GET"])
@login_required
@no_cache
def get_settings_endpoint():
    return get_settings(user_id=session["user"]["id"])


@app.route("/api/settings/<key>/<value>", methods=["GET"])
@login_required
@no_cache
def settings_endpoint(key, value):
    value = True if value == "true" else False

    if key == "adult-result" or key == "ignore-overs":
        return set_settings(user_id=session["user"]["id"], key=key, value=value)
    return jsonify({"status": "error", "value": not value}), 400


@app.route("/favicon.ico")
@app.route("/robots.txt")
@app.route("/humans.txt")
@app.route("/manifest.json")
@app.route("/sw.js")
def static_from_root():
    """Serves static files from the static/root directory.

    This view is used to serve static files from the static/root directory. It
    is used to serve the favicon, robots.txt, humans.txt, and manifest.json
    files. The cached version of this view is used to reduce the number of
    requests to the server.
    """
    return send_from_directory("static/root", request.path[1:])


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.route("/500")
def server_error():
    abort(500)


@app.errorhandler(500)
def internal_server_error(e):
    from discord_webhook import DiscordWebhook, DiscordEmbed
    import traceback

    webhook = DiscordWebhook(
        url=os.getenv("DISCORD_WEBHOOK_URL"),
        username="OeuvresTrack",
        avatar_url="https://oeuvrestrack.vercel.app/static/icons/pwa/logo_192.png",
    )
    webhook.add_embed(
        DiscordEmbed(
            title="500 Internal Server Error",
            description=f"url : {request.url}\n\n```py\n{traceback.format_exc()}\n```",
            color=0xFF0000,
        )
    )
    webhook.execute()

    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(debug=debug, host="0.0.0.0", port=7000)
