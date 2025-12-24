import requests, cloudscraper, html, re, json, os
from pymongo import MongoClient, UpdateOne
from passlib.hash import pbkdf2_sha256
from datetime import date, timedelta
from bs4 import BeautifulSoup

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")

scraper = cloudscraper.create_scraper()
db = MongoClient(os.getenv("MONGODB_URI")).OeuvresTrack

tmdb_headers = {
    "accept": "application/json",
    "Authorization": os.getenv("TMDB_TOKEN"),
}


def check_element(id: int) -> bool:
    """
    Vérifie si une oeuvre est déjà dans la base de données.

    Parameters
    ----------
    id : int
        ID TMDB de l'oeuvre

    Returns
    -------
    bool
        True si l'oeuvre est déjà dans la base de données, False sinon
    """
    return db.catalog.count_documents({"id": int(id)}) > 0


def check_element_by_original_id(type: str, original_id) -> bool:
    """
    Vérifie si une oeuvre est déjà dans la base de données.

    Parameters
    ----------
    type : str
        Type de l'oeuvre (movie, tv, book)
    original_id : int or str
        ID original de l'oeuvre (ID TMDB, ISBN, etc.)

    Returns
    -------
    bool
        True si l'oeuvre est déjà dans la base de données, False sinon
    """
    return db.catalog.count_documents({"original_id": original_id, "type": type}) > 0


def get_element(type: str, id: int) -> dict:
    """
    Renvoie les informations d'une oeuvre en fonction de son type et de son ID TMDB

    Parameters
    ----------
    type : str
        Type de l'oeuvre (movie, tv, book)
    id : int
        ID TMDB de l'oeuvre

    Returns
    -------
    dict
        Informations de l'oeuvre, sans l'_id
    """
    return db.catalog.find_one({"id": int(id), "type": type}, {"_id": 0})


def get_element_by_original_id(type: str, original_id) -> dict:
    """
    Renvoie les informations d'une oeuvre en fonction de son type et de son ID original

    Parameters
    ----------
    type : str
        Type de l'oeuvre (movie, tv, book)
    original_id : int or str
        ID original de l'oeuvre (ID TMDB, ISBN, etc.)

    Returns
    -------
    dict
        Informations de l'oeuvre, sans l'_id
    """
    return db.catalog.find_one({"original_id": original_id, "type": type}, {"_id": 0})


def add_element(element: dict):
    """
    Ajoute un élément à la base de données.

    Parameters
    ----------
    element : dict
        Informations de l'oeuvre à ajouter
    """

    db.catalog.insert_one(element.copy())


def search_new_movie(query: str, user_id: int) -> dict:
    """
    Recherche un film par son titre sur TMDB et renvoie les résultats

    Parameters
    ----------
    query : str
        Le titre du film
    user_id : int
        L'identifiant de l'utilisateur

    Returns
    -------
    dict
        Les résultats de la recherche, avec les clés
            - source (str): tmdb
            - type (str): movie
            - terms (str): La requête de recherche
            - results (list): Une liste de résultats, avec une seule entrée
                - title (str): Un titre générique
                - contents (list): La liste des résultats de la recherche sur TMDB
    """
    settings = get_settings(user_id=user_id)
    include_adult = "include_adult" in settings and settings["include_adult"]

    results = requests.get(
        f"https://api.themoviedb.org/3/search/movie?query={query}&include_adult={str(include_adult)}&language=fr-FR&page=1",
        headers=tmdb_headers,
    ).json()
    results["source"] = "tmdb"
    results["type"] = "movie"
    results["terms"] = query
    results["results"] = [
        {
            "title": "Resultats des films :",
            "contents": results["results"],
        }
    ]
    return results


def get_movie_by_id(id: str) -> dict:
    """Recherche un film par son identifiant sur TMDB et renvoie les resultats

    Args:
        id (str): L'identifiant du film sur TMDB

    Returns:
        dict: Les resultats de la recherche, avec les cles
            - source (str): tmdb
            - type (str): movie
            - terms (str): La requete de recherche
            - results (list): Une liste de resultats, avec une seule entree
                - title (str): Un titre generique
                - contents (list): La liste des resultats de la recherche sur TMDB
    """
    results = requests.get(
        f"https://api.themoviedb.org/3/movie/{str(id)}?language=fr-FR",
        headers=tmdb_headers,
    ).json()
    if "success" in results and not results["success"]:
        return None
    results["image"] = {
        "backdrop": results["backdrop_path"],
        "poster": results["poster_path"],
    }
    results["source"] = "tmdb"
    return results


def search_new_tv(query: str, user_id: int) -> dict:
    """Recherche une série par son titre sur TMDB et renvoie les resultats

    Args:
        query (str): Le titre de la série
        user_id (int): L'identifiant de l'utilisateur

    Returns:
        dict: Les resultats de la recherche, avec les cles
            - source (str): tmdb
            - type (str): tv
            - terms (str): La requete de recherche
            - results (list): Une liste de resultats, avec une seule entree
                - title (str): Un titre generique
                - contents (list): La liste des resultats de la recherche sur TMDB
    """
    settings = get_settings(user_id=user_id)
    include_adult = "include_adult" in settings and settings["include_adult"]

    results = requests.get(
        f"https://api.themoviedb.org/3/search/tv?query={query}&include_adult={str(include_adult)}&language=fr-FR&page=1",
        headers=tmdb_headers,
    ).json()
    results["source"] = "tmdb"
    results["type"] = "tv"
    results["terms"] = query
    results["results"] = [
        {
            "title": "Resultats des séries :",
            "contents": results["results"],
        }
    ]
    return results


def get_tv_season_by_id(id: str, season_number: int) -> dict:
    """Recherche une saison de série par son identifiant et le numéro de la saison sur TMDB et renvoie les resultats

    Args:
        id (str): L'identifiant de la série sur TMDB
        season_number (int): Le numéro de la saison

    Returns:
        dict: Les resultats de la recherche sur TMDB
    """
    return requests.get(
        f"https://api.themoviedb.org/3/tv/{str(id)}/season/{str(season_number)}?language=fr-FR",
        headers=tmdb_headers,
    ).json()


def get_info_about_season(id: int, season_number: int):
    """
    Renvoie les informations sur une saison de série en fonction de son identifiant et de son numéro

    Parameters
    ----------
    id : int
        L'identifiant de la série sur TMDB
    season_number : int
        Le numéro de la saison

    Returns
    -------
    dict
        Les informations sur la saison, contenant :
            - title (str): Le titre de la saison
            - image (str): L'URL de l'image de la saison
            - overview (str): Le résumé de la saison
            - season_number (int): Le numéro de la saison
            - air_date (str): La date de diffusion de la saison
            - contents (list): La liste des épisodes de la saison
            - last_update (str): La date de dernière mise à jour
            - recommandate_update (str): La date de prochaine mise à jour recommandée
            - finished (bool): Si la saison est terminée
    """
    season_data = get_tv_season_by_id(id, season_number)

    finished = True
    last_air = None

    for episode in season_data["episodes"]:
        if (
            episode["air_date"] is None
            or episode["air_date"] > date.today().isoformat()
        ):
            finished = False
            last_air = episode["air_date"]
            break

    recommandate_update = (date.today() + timedelta(days=30)).isoformat()
    if not finished:
        recommandate_update = (
            last_air if last_air else (date.today() + timedelta(days=7)).isoformat()
        )

    season = {
        "title": season_data["name"],
        "image": season_data["poster_path"],
        "overview": season_data["overview"],
        "season_number": season_data["season_number"],
        "air_date": season_data["air_date"],
        "contents": [],
        "last_update": date.today().isoformat(),
        "recommandate_update": recommandate_update,
        "finished": finished,
    }
    for episode in season_data["episodes"]:
        season["contents"].append(episode["name"])

    return season


def get_tv_by_id(id: str) -> dict:
    """Recherche une série par son identifiant sur TMDB et renvoie les resultats

    Args:
        id (str): L'identifiant de la série sur TMDB

    Returns:
        dict: Les resultats de la recherche, avec les cles
            - source (str): tmdb
            - type (str): tv
            - terms (str): La requete de recherche
            - results (list): Une liste de resultats, avec une seule entree
                - title (str): Un titre generique
                - contents (list): La liste des resultats de la recherche sur TMDB
    """
    results = requests.get(
        f"https://api.themoviedb.org/3/tv/{str(id)}?language=fr-FR",
        headers=tmdb_headers,
    ).json()
    if "success" in results and not results["success"]:
        return None

    results["contents"] = results["seasons"].copy()
    for i, season in enumerate(results["contents"]):
        element = get_info_about_season(id, season["season_number"])

        results["contents"][i] = element

    if results["contents"][0]["season_number"] == 0:
        results["contents"].append(results["contents"].pop(0))

    results["source"] = "tmdb"
    results["image"] = {
        "backdrop": results["backdrop_path"],
        "poster": results["poster_path"],
    }
    del results["seasons"]
    return results


def search_new_book(query) -> dict:
    """Cherche un livre sur Booknode et renvoie les resultats

    Args:
        query (str): Le nom du livre a chercher

    Returns:
        dict: Les resultats de la recherche, avec les cles
            - source (str): booknode
            - type (str): book
            - terms (str): La requete de recherche
            - results (list): Une liste de resultats, avec deux entrees
                - title (str): Un titre generique
                - contents (list): La liste des resultats de la recherche sur Booknode
    """

    results: dict = scraper.get(
        f"https://booknode.com/search-json?q={query.lower().replace(' ', '+')}&exclude_series_from_books=1"
    ).json()
    results["source"] = "booknode"
    results["type"] = "book"

    del results["authors"]
    del results["themes"]
    del results["users"]

    results["results"] = [
        {"title": "Resultats des séries de livres :", "contents": results["series"]},
        {"title": "Resultats des livres uniques :", "contents": results["books"]},
    ]
    for i, result in enumerate(results["results"]):
        for cont in result["contents"]:
            if i == 0:
                cont["type"] = "books"
                cont["id"] = cont["href"].split("/")[-1]
            else:
                cont["type"] = "book"

    del results["books"]
    del results["series"]
    return results


def get_book_by_id(id: str) -> dict:
    """Cherche un livre sur Booknode et renvoie ses informations

    Args:
        id (str): L'ID du livre sur Booknode

    Returns:
        dict: Les informations du livre, avec les cles
            - title (str): Le titre du livre
            - overview (str): Un résumé du livre
            - image (str): L'URL de la couverture du livre
    """
    while len(str(id)) < 8:
        id = "0" + str(id)
    result = scraper.get("https://booknode.com/id_" + id)
    if result.status_code != 200:
        return None
    soup = BeautifulSoup(result.text, "html.parser")

    try:
        img_container = soup.find("div", {"class": "foreground"})
        basic_image = img_container.find("img").attrs["src"]
        basic_image = basic_image.replace(".jpg", ".webp").replace(".png", ".webp")
    except AttributeError:
        print(f"No image found for book {id}")
        basic_image = ""
        
    
    r = {
        "title": html.unescape(
            soup.h1.text
        ),
        "overview": html.unescape(
            soup.h1.parent.find("span", {"class": "actual-text"}).text.replace("Résumé", "").strip()
        ).removesuffix("\n"),
        "image": {
            "264": basic_image,
            "121": basic_image.replace("264-432", "121-198"),
            "66": basic_image.replace("264-432", "66-108"),
            "30": basic_image.replace("264-432", "30-40"),
        },
        "source": "booknode",
        "id": int(id),
    }
    return r


def get_books_by_id(id: str) -> dict:
    """
    Cherche un ensemble de livres sur Booknode et renvoie leurs informations

    Args:
        url (str): L'URL de l'ensemble de livres sur Booknode

    Returns:
        dict: Les informations de l'ensemble de livres, avec les cles
            - title (str): Le titre de l'ensemble de livres
            - overview (str): Un résumé de l'ensemble de livres
            - image (dict): Les URL de la couverture de l'ensemble de livres en
              différentes tailles
            - tomes (list): La liste des titres des livres de l'ensemble
    """
    result = scraper.get("https://booknode.com/serie/" + str(id))
    if result.status_code != 200:
        return None
    soup = BeautifulSoup(result.text, "html.parser")
    
    basic_image = soup.find("article", {"class": "liste"}).find("img").attrs["data-src"].replace(".jpg", ".webp").replace(".png", ".webp")
    r = {
        "title": html.unescape(
            soup.h1.find("span").text
        ),
        "overview": re.sub(
            " +",
            " ",
            html.unescape(
                soup.find("div", {"class": "js-readmore", "data-maxwords": "50", "data-maxchars": "240"}).text
            ),
        )
        .removesuffix("\n ")
        .removeprefix("\n "),
        "image": {
            "264": basic_image,
            "121": basic_image.replace("264-432", "121-198"),
            "66": basic_image.replace("264-432", "66-108"),
            "30": basic_image.replace("264-432", "30-40"),
        },
        "source": "booknode",
        "id": id,
    }
    r["contents"] = [{"title": "Tomes :", "contents": []}]
    for i in (
        soup.find("article", {"class": "liste"}).find_all("div", {"class": "book col-xs-12 col-xs1-12 col-sm-12"})
    ):
        r["contents"][0]["contents"].append(
            html.unescape(i.find("a").attrs["title"])
        )
    return r


def get_new_catalog_id() -> int:
    """
    Retourne un nouvel ID pour la base de données, et l'incrémente.

    Returns:
        int: Le nouvel ID
    """
    db.get_collection("ids").update_one(
        {"collection": "catalog"}, {"$inc": {"id": 1}}, upsert=True
    )
    return db.get_collection("ids").find_one({"collection": "catalog"}, {"id": 1})["id"]


def get_new_users_id() -> int:
    """
    Retourne un nouvel ID pour la base de données, et l'incrémente.

    Returns:
        int: Le nouvel ID
    """
    db.get_collection("ids").update_one(
        {"collection": "users"}, {"$inc": {"id": 1}}, upsert=True
    )
    return db.get_collection("ids").find_one({"collection": "users"}, {"id": 1})["id"]


def get_recommandate_date(data: dict, type: str) -> str:
    """
    Retourne la date de recommandation de rechangement du contenu d'un élément de la base de données

    Args:
        data (dict): Les données de l'élément
        type (str): Le type de l'élément (tv, movie, book ou books)

    Returns:
        str: La date de recommandation au format ISO 8601
    """
    recommandate_update = (date.today() + timedelta(days=30)).isoformat()
    if type == "tv":
        if (
            data["first_air_date"] is not None
            or date["first_air_date"] != ""
            and (date.fromisoformat(data["first_air_date"]) + timedelta(days=14))
            > date.today()
        ):
            recommandate_update = (date.today() + timedelta(days=7)).isoformat()
    elif type == "movie":
        if (
            data["release_date"] is not None
            or date["first_air_date"] != ""
            and (date.fromisoformat(data["release_date"]) + timedelta(days=14))
            > date.today()
        ):
            recommandate_update = (date.today() + timedelta(days=7)).isoformat()
        else:
            recommandate_update = (date.today() + timedelta(days=60)).isoformat()
    elif type == "book":
        recommandate_update = (date.today() + timedelta(days=60)).isoformat()
    elif type == "books":
        recommandate_update = (date.today() + timedelta(days=7)).isoformat()

    return recommandate_update


def get_new_element(type: str, id: str) -> dict:
    """
    Cherche un élément sur TMDB ou Booknode, si il n'existe pas dans la base de données,
    l'ajoute avec un nouvel ID

    Args:
        type (str): Le type de l'élément (movie, tv, book, books)
        id (str): L'ID de l'élément sur TMDB ou Booknode

    Returns:
        dict: Les informations de l'élément, avec les clés id, title, overview, type, image, source, original_id, contents
    """
    if isinstance(id, str):
        if id.isdigit():
            id = int(id)

    is_exist = check_element_by_original_id(type, id)

    if not is_exist:
        if type == "movie":
            data = get_movie_by_id(id)
        elif type == "tv":
            data = get_tv_by_id(id)
        elif type == "book":
            data = get_book_by_id(id)
        elif type == "books":
            data = get_books_by_id(id)
        else:
            return None

        if data is None:
            return None

        if type in ["movie", "book", "books"]:
            title = data["title"]
        else:
            title = data["name"]

        element = {
            "id": get_new_catalog_id(),
            "title": title,
            "overview": data["overview"],
            "type": type,
            "image": data["image"],
            "source": data["source"],
            "original_id": data["id"],
            "last_update": date.today().isoformat(),
            "recommandate_update": get_recommandate_date(data, type),
        }
        if type == "books" or type == "tv":
            finished = True

            element["contents"] = data["contents"]
            if type == "tv":
                for i in data["contents"]:
                    if i["finished"] is False:
                        finished = False
                element["finished"] = finished

        add_element(element)

        return element

    if isinstance(id, str):
        if id.isdigit():
            return get_element_by_original_id(type, int(id))
    return get_element_by_original_id(type, id)


def check_password(password, encrypt_password):
    return pbkdf2_sha256.verify(password, encrypt_password)


def encrypt_password(password):
    return pbkdf2_sha256.encrypt(password)


def markdown_to_html(text) -> str:
    """
    Convertit un texte en markdown en HTML

    Args:
        text (str): Le texte en markdown

    Returns:
        str: Le texte en HTML
    """

    # Convertir le texte en gras (**bold** ou __bold__)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"<strong>\2</strong>", text)

    # Convertir le texte en italique (*italic* ou _italic_)
    text = re.sub(r"(\*|_)(.*?)\1", r"<em>\2</em>", text)

    # Convertir le texte barré (~~strikethrough~~)
    text = re.sub(r"~~(.*?)~~", r"<del>\1</del>", text)

    # Convertir le texte souligné (++underline++)
    text = re.sub(r"\+\+(.*?)\+\+", r"<u>\1</u>", text)

    return text


def get_user_ulist(id: int) -> list:
    """Renvoie la liste des éléments de l'utilisateur d'ID id

    Args:
        id (int): L'ID de l'utilisateur

    Returns:
        list: La liste des éléments de l'utilisateur
    """

    pipeline = [
        # Étape 1 : Filtrer par _id
        {"$match": {"id": id}},
        # Étape 2 : Décomposer la liste `list`
        {"$unwind": "$list"},
        # Étape 3 : Rejoindre avec `catalog` sur `id` et `type`
        {
            "$lookup": {
                "from": "catalog",  # Collection à joindre
                "let": {
                    "list_id": "$list.id",  # ID de l'élément dans `list`
                    "list_type": "$list.type",  # Type de l'élément dans `list`
                },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$type", "$$list_type"]},  # Match type
                                    {
                                        "$eq": [
                                            "$original_id",
                                            "$$list_id",
                                        ]
                                    },
                                ]
                            }
                        }
                    },
                    {
                        "$project": {  # Ne garder que les champs nécessaires
                            "_id": 0,
                            "image": 1,
                            "overview": 1,
                            "title": 1,
                        }
                    },
                ],
                "as": "catalog_info",
            }
        },
        # Étape 4 : Filtrer pour ne garder que les catalogues trouvés
        {"$match": {"catalog_info": {"$ne": []}}},
        # Étape 5 : Simplifier la structure des résultats
        {
            "$project": {
                "_id": 0,
                "id": "$list.id",
                "type": "$list.type",
                "text": "$list.text",
                "checked": "$list.checked",
                "status": "$list.status",
                "catalog": {
                    "$arrayElemAt": ["$catalog_info", 0]
                },  # Prendre le premier élément trouvé
            }
        },
    ]
    results = db.ulist.aggregate(pipeline)
    return list(results)


default_lexicon = {
    "OnFinishStatus": [
        {"text": "~~", "position": 0},
        {"text": "~~", "position": 6},
    ],
    "OnTitle": [
        {"text": "{0}", "position": 1},
    ],
    "OnUnfinishedSeason": [
        {"text": "*s{0}*", "position": 2, "disabled": True},
    ],
    "OnFinishSeason": [
        {"text": "s{0}", "position": 2, "disabled": True},
    ],
    "OnStartedSeason": [
        {"text": "s{0}", "position": 2},
    ],
    "OnTome": [
        {"text": "t{0}/t{1}", "position": 2},
    ],
    "OnEpisode": [
        {"text": "e{0}", "position": 3},
    ],
    "OnRank": [
        {"text": "**{0}r**", "position": 5},
    ],
    "OnGiveUp": [
        {"text": "~~", "position": 0},
        {"text": "(abandonné)~~", "position": 6},
    ],
    "OnUnFinishedRelease": [{"text": "*(pas finit de sortir)*", "position": 4}],
}


def get_ulist_text(catalog, ucatalog=None, lexicon={}) -> str:
    """
    Convertit un élément de la liste de l'utilisateur en texte markdown, en remplaçant les éléments du lexique par les valeurs appropriées

    Args:
        catalog (dict): L'élément de la liste
        ucatalog (dict, optional): L'élément de l'utilisateur. Defaults to None.
        settings (dict, optional): Les paramètres de l'utilisateur. Defaults to None.

    Returns:
        str: Le texte markdown
    """
    elements = []

    if lexicon == {}:
        lexicon = default_lexicon.copy()

    for i in lexicon["OnTitle"]:
        if "disabled" not in i:
            elements.append(
                {"text": i["text"].format(catalog["title"]), "position": i["position"]}
            )
    if catalog["type"] == "tv":
        for i in lexicon["OnStartedSeason"]:
            if "disabled" not in i:
                if ucatalog is not None:
                    for index, j in enumerate(ucatalog["watch"]):
                        if len(j["watched"]) > 0:
                            elements.append(
                                {
                                    "text": i["text"].format(j["season_number"]),
                                    "position": i["position"],
                                    "season_number": j["season_number"],
                                }
                            )

    if catalog["type"] == "tv":
        for i in lexicon["OnFinishSeason"]:
            if "disabled" not in i:
                if ucatalog is not None:
                    for index, j in enumerate(ucatalog["watch"]):
                        if len(j["watched"]) == 1:
                            if j["watched"][0].split("-") == [
                                "1",
                                str(len(catalog["contents"][index]["contents"])),
                            ]:
                                elements.append(
                                    {
                                        "text": i["text"].format(j["season_number"]),
                                        "position": i["position"],
                                        "season_number": j["season_number"],
                                    }
                                )

    if catalog["type"] == "tv":
        for i in lexicon["OnUnfinishedSeason"]:
            if "disabled" not in i:
                if ucatalog is None:
                    for j in catalog["contents"]:
                        elements.append(
                            {
                                "text": i["text"].format(j["season_number"]),
                                "position": i["position"],
                                "season_number": j["season_number"],
                            }
                        )
                else:
                    for index, j in enumerate(ucatalog["watch"]):
                        if len(j["watched"]) > 0:
                            if j["watched"][0].split("-") != [
                                "1",
                                str(len(catalog["contents"][index]["contents"])),
                            ]:
                                elements.append(
                                    {
                                        "text": i["text"].format(j["season_number"]),
                                        "position": i["position"],
                                        "season_number": j["season_number"],
                                    }
                                )
        if not catalog["finished"]:
            for i in lexicon["OnUnFinishedRelease"]:
                if "disabled" not in i:
                    elements.append(
                        {
                            "text": i["text"],
                            "position": i["position"],
                        }
                    )

    if ucatalog is not None:
        if ucatalog["status"] == "done":
            for i in lexicon["OnFinishStatus"]:
                if "disabled" not in i:
                    elements.append(
                        {
                            "text": i["text"],
                            "position": i["position"],
                        }
                    )

    if catalog["type"] == "books":
        for i in lexicon["OnTome"]:
            if "disabled" not in i:
                if ucatalog is not None:
                    tome = 0
                    if len(ucatalog["watch"][0]["watched"]) > 0:
                        tome = int(ucatalog["watch"][0]["watched"][-1].split("-")[-1])

                    elements.append(
                        {
                            "text": i["text"].format(
                                tome,
                                len(catalog["contents"][0]["contents"]),
                            ),
                            "position": i["position"],
                        }
                    )
                else:
                    elements.append(
                        {
                            "text": i["text"].format(
                                0,
                                len(catalog["contents"][0]["contents"]),
                            ),
                            "position": i["position"],
                        }
                    )
    if catalog["type"] == "tv":
        if ucatalog is not None:
            for i in lexicon["OnEpisode"]:
                if "disabled" not in i:
                    last_started_season = 0
                    for j in range(len(ucatalog["watch"])):
                        if len(ucatalog["watch"][j]["watched"]) > 0:
                            last_started_season = j

                    if len(ucatalog["watch"]) > 0:
                        if (
                            len(
                                ucatalog["watch"][last_started_season].get(
                                    "watched", ["0"]
                                )
                            )
                            == 0
                        ):
                            ucatalog["watch"][last_started_season]["watched"] = ["0"]
                    else:
                        ucatalog["watch"].append(
                            {
                                "watched": ["0"],
                            }
                        )

                    if (
                        int(
                            ucatalog["watch"][last_started_season]
                            .get("watched", ["0"])[-1]
                            .split("-")[-1]
                        )
                        == 0
                    ):
                        continue

                    elements.append(
                        {
                            "text": i["text"].format(
                                int(
                                    ucatalog["watch"][last_started_season]
                                    .get("watched", ["0"])[-1]
                                    .split("-")[-1]
                                )
                            ),
                            "position": i["position"],
                        }
                    )

    if ucatalog is not None:
        if ucatalog["rank"] is not None:
            for i in lexicon["OnRank"]:
                if "disabled" not in i:
                    if ucatalog["rank"] != "":
                        elements.append(
                            {
                                "text": i["text"].format(ucatalog["rank"]),
                                "position": i["position"],
                            }
                        )

    if ucatalog is not None:
        if ucatalog["status"] == "giveup":
            for i in lexicon["OnGiveUp"]:
                if "disabled" not in i:
                    elements.append(
                        {
                            "text": i["text"],
                            "position": i["position"],
                        }
                    )

    text = ""
    elements.sort(key=lambda x: x["position"])
    for e in elements:
        if type(e) == list:
            for i in e:
                text += i["text"] + " "
        else:
            text += e["text"] + " "

    return markdown_to_html(text.removesuffix(" "))


def add_ulist(user_id: int, type: str, id: str):
    """
    Ajoute un élément à la liste de l'utilisateur

    Args:
        user_id (int): L'ID de l'utilisateur
        type (str): Le type de l'élément (movie, tv, book, books)
        id (str, int): L'ID de l'élément sur TMDB ou Booknode

    Returns:
        bool: True si l'élément a été ajouté, False sinon
    """
    if isinstance(id, str):
        if id.isdigit():
            id = int(id)

    if db.ucatalog.count_documents({"user_id": user_id, "type": type, "id": id}) > 0:
        return False

    dcatalog = db.catalog.find_one(
        {"original_id": id, "type": type},
        {
            "title": 1,
            "image": 1,
            "type": 1,
            "contents": 1,
            "original_id": 1,
            "finished": 1,
            "overview": 1,
        },
    )
    if dcatalog is None:
        return None

    text = get_ulist_text(dcatalog, lexicon=get_lexicon(user_id))

    db.ulist.update_one(
        {"id": user_id},
        {
            "$push": {
                "list": {
                    "id": dcatalog["original_id"],
                    "type": dcatalog["type"],
                    "text": text,
                    "checked": False,
                    "status": "towatch",
                }
            }
        },
        upsert=True,
    )
    db.ucatalog.insert_one(
        {
            "user_id": user_id,
            "type": type,
            "id": id,
            "watch": [],
            "rank": "",
            "status": "towatch",
        }
    )
    return {
        "text": text,
        "type": type,
        "id": id,
        "status": "towatch",
        "checked": False,
        "catalog": {
            "image": dcatalog["image"],
            "title": dcatalog["title"],
            "overview": dcatalog["overview"],
        },
    }


def hard_reload(user_id: int):
    ulist = db.ulist.find_one({"id": user_id}, {"list": 1})
    settings = get_settings(user_id)

    lexicon = (
        default_lexicon.copy() if settings["lexicon"] == {} else settings["lexicon"]
    )

    if len(ulist["list"]) == 0:
        return ulist["list"]

    pipeline = [
        {
            "$match": {
                "$or": [
                    {"user_id": user_id, "id": i["id"], "type": i["type"]}
                    for i in ulist["list"]
                ]
            }
        },
        {
            "$lookup": {
                "from": "catalog",
                "localField": "type",
                "foreignField": "type",
                "as": "catalog_info",
                "let": {"id": "$id"},
                "pipeline": [{"$match": {"$expr": {"$eq": ["$original_id", "$$id"]}}}],
            }
        },
        {"$unwind": "$catalog_info"},
        {
            "$project": {
                "watch": 1,
                "rank": 1,
                "status": 1,
                "id": 1,
                "type": 1,
                "catalog_info.contents": 1,
                "catalog_info.title": 1,
                "catalog_info.type": 1,
                "catalog_info.finished": 1,
            }
        },
    ]

    results = db.ucatalog.aggregate(pipeline)

    operation = []

    for result in results:
        ucatalog = {
            "watch": result.get("watch"),
            "rank": result.get("rank"),
            "status": result.get("status"),
        }
        catalog = result["catalog_info"]
        previous_status = ucatalog["status"]

        ucatalog["status"] = get_status(
            catalog=catalog, ucatalog=ucatalog, settings=settings
        )

        if previous_status != ucatalog["status"]:
            operation.append(
                UpdateOne(
                    {"user_id": user_id, "type": result["type"], "id": result["id"]},
                    {"$set": {"status": ucatalog["status"]}},
                )
            )

        for i in ulist["list"]:
            if i["id"] == result["id"] and i["type"] == result["type"]:
                i["checked"] = ucatalog["status"] in ["done", "giveup"]
                i["text"] = get_ulist_text(catalog, ucatalog=ucatalog, lexicon=lexicon)

    if operation:
        db.catalog.bulk_write(operation)

    db.ulist.update_one(
        {"id": user_id},
        {"$set": {"list": ulist["list"]}},
    )

    return ulist["list"]


def remove_ulist(user_id: int, type: str, id: str):
    """
    Supprime un élément de la liste de l'utilisateur

    Args:
        user_id (int): L'ID de l'utilisateur
        type (str): Le type de l'élément (movie, tv, book, books)
        id (str, int): L'ID de l'élément sur TMDB ou Booknode

    Returns:
        bool: True si l'élément a été supprimé, False sinon
    """
    if isinstance(id, str):
        if id.isdigit():
            id = int(id)

    if db.ucatalog.count_documents({"user_id": user_id, "type": type, "id": id}) == 0:
        return False

    db.ucatalog.delete_one({"user_id": user_id, "type": type, "id": id})
    db.ulist.update_one(
        {"id": user_id},
        {"$pull": {"list": {"id": id, "type": type}}},
    )
    return True


def get_ucatalog(user_id: int, type: str, id: str):
    """
    Renvoie un élément de la liste de l'utilisateur

    Parameters
    ----------
    user_id : int
        L'ID de l'utilisateur
    type : str
        Le type de l'élément (movie, tv, book, books)
    id : str, int
        L'ID de l'élément sur TMDB ou Booknode

    Returns
    -------
    dict
        Les informations de l'élément, sans l'ID, le type et l'ID de l'utilisateur.
        Le dictionnaire contient la clé "exist" qui vaut True si l'élément existe,
        False sinon.
    """

    if isinstance(id, str):
        if id.isdigit():
            id = int(id)
    data = db.ucatalog.find_one({"user_id": user_id, "id": id, "type": type})
    if data is None:
        return {"exist": False}
    del data["id"]
    del data["_id"]
    del data["type"]
    data["exist"] = True
    return data


def valid_format_ucatalalog(chaine):
    """
    Vérifie si le format de la chaine est valide pour être utilisé
    comme ID pour un élément de la liste de l'utilisateur.

    Un format valide est un entier, ou un entier suivi d'un tiret
    et d'un autre entier plus grand.

    Exemples de formats valides :
    - 1
    - 1-2
    - 1-4

    Exemples de formats invalides :
    - 1-a
    - 1-0
    - 1-1
    - a-1

    Parameters
    ----------
    chaine : str
        La chaine à vérifier

    Returns
    -------
    bool
        True si le format est valide, False sinon
    """
    pattern = r"^(\d+)(?:-(\d+))?$"

    match = re.match(pattern, chaine)
    if match:
        nombre1 = int(match.group(1))
        nombre2 = match.group(2)

        if nombre2 is None:
            return True
        else:
            nombre2 = int(nombre2)
            if nombre2 > nombre1:
                return True

    return False


def get_status(
    catalog: dict, ucatalog: dict, ignore_giveup: bool = False, settings: dict = {}
) -> str:
    """
    Détermine le status d'une oeuvre en fonction de son type et de l'état de sa lecture/écoutage

    Parameters
    ----------
    catalog : dict
        Informations de l'oeuvre
    ucatalog : dict
        Informations de l'utilisateur sur l'oeuvre
    ignore_giveup : bool, optional
        Si True, ignore le status giveup, par défaut False
    settings : dict, optional
        Paramètres de l'utilisateur, par défaut {}

    Returns
    -------
    str
        Status de l'oeuvre :
        - towatch si l'oeuvre n'a pas encore été lue/écoutée
        - onwatch si l'oeuvre est en cours de lecture/écoutage
        - done si l'oeuvre a été lue/écoutée
        - giveup si l'utilisateur a abandonné l'oeuvre
    """
    ignore_overs = True
    if "ignore-overs" in settings:
        ignore_overs = settings["ignore-overs"]

    status = ucatalog["status"]
    if status == "giveup" and not ignore_giveup:
        return status

    finished = True
    started = False

    if catalog["type"] == "tv" or catalog["type"] == "books":
        for i, s in enumerate(catalog["contents"]):
            if catalog["type"] == "tv":
                uelement = next(
                    (
                        e
                        for e in ucatalog["watch"]
                        if e["season_number"] == str(s["season_number"])
                    ),
                    {},
                )

                if s["season_number"] == 0 and ignore_overs:
                    continue
            else:
                uelement = next(iter(ucatalog["watch"]), {})

            if uelement == {}:
                if (len(s["contents"]) > 0 and s["finished"] is True) or len(
                    s["contents"]
                ) > 1:
                    finished = False
                continue

            if len(uelement["watched"]) > 0:
                started = True

            if len(uelement["watched"]) == 1:
                if int(uelement["watched"][0].split("-")[-1]) != len(s["contents"]):
                    finished = False
            elif (len(s["contents"]) > 0 and s["finished"] is True) or len(
                s["contents"]
            ) > 1:
                finished = False
    else:
        finished = ucatalog["watch"]

    status = ucatalog["status"]

    if finished:
        status = "done"
    elif started:
        status = "onwatch"
    else:
        status = "towatch"

    return status


def send_update_ucatalog(catalog, ucatalog):
    settings = get_settings(user_id=ucatalog["user_id"])
    lexicon = default_lexicon.copy() if settings is None else settings["lexicon"]

    ucatalog["status"] = get_status(
        catalog=catalog, ucatalog=ucatalog, settings=settings
    )

    # Update ucatalog and ulist
    db.ucatalog.update_one(
        {
            "user_id": ucatalog["user_id"],
            "id": catalog["original_id"],
            "type": catalog["type"],
        },
        {"$set": {"watch": ucatalog["watch"], "status": ucatalog["status"]}},
    )
    text = get_ulist_text(catalog, ucatalog, lexicon)
    db.ulist.update_one(
        {
            "id": ucatalog["user_id"],
            "list": {
                "$elemMatch": {"id": catalog["original_id"], "type": catalog["type"]}
            },
        },
        {
            "$set": {
                "list.$.text": text,
                "list.$.status": ucatalog["status"],
                "list.$.checked": ucatalog["status"] == "done"
                or ucatalog["status"] == "giveup",
            }
        },
    )

    return {"status": ucatalog["status"], "text": text}


def update_ucatalog(
    user_id: int, type: str, id, season_number: int, changes: list | bool
):
    """
    Met à jour un élément de la liste de l'utilisateur

    Parameters
    ----------
    user_id : int
        L'ID de l'utilisateur
    type : str
        Le type de l'élément (movie, tv, book, books)
    id : str, int
        L'ID de l'élément sur TMDB ou Booknode
    season_number : int
        Le numéro de la saison
    changes : list | bool
        Les modifications à apporter, True pour tout marquer comme regardé,
        False pour tout marquer comme non-regardé, ou une liste de chaines
        représentant les épisodes à regarder, au format 1-2, 1-4, etc.

    Returns
    -------
    dict
        Les informations de l'élément mis à jour, sans l'ID, le type et
        l'ID de l'utilisateur.

    Raises
    ------
    ValueError
        Si le format de changes est invalide
    """
    if isinstance(changes, list):
        for s in changes:
            if not valid_format_ucatalalog(s):
                return {"status": "error"}
    elif not isinstance(changes, bool):
        return {"status": "error"}

    # convert id to int if needed
    if isinstance(id, str):
        if id.isdigit():
            id = int(id)

    # get ucatalog if not exist create it
    ucatalog = get_ucatalog(user_id=user_id, type=type, id=id)
    if ucatalog["exist"] is False:
        add_ulist(user_id, type, id)
        ucatalog = get_ucatalog(user_id=user_id, type=type, id=id)

    # update and check changes
    if type == "tv" or type == "books":
        index_of_season = None
        for i, s in enumerate(ucatalog["watch"]):
            if s["season_number"] == season_number:
                index_of_season = i
                break

        if index_of_season is None:
            ucatalog["watch"].append({"season_number": season_number})
            index_of_season = ucatalog["watch"].index({"season_number": season_number})

        ucatalog["watch"][index_of_season]["watched"] = changes
    else:
        ucatalog["watch"] = changes

    catalog = db.get_collection("catalog").find_one(
        {"original_id": id, "type": type},
        {
            "title": 1,
            "type": 1,
            "contents": 1,
            "finished": 1,
            "original_id": 1,
            "type": 1,
        },
    )

    result = send_update_ucatalog(catalog, ucatalog)
    ucatalog["status"] = result["status"]
    checked = ucatalog["status"] == "done" or ucatalog["status"] == "giveup"

    return {
        "text": result["text"],
        "type": type,
        "id": id,
        "status": ucatalog["status"],
        "checked": checked,
    }


def toggle_giveup(user_id: int, type: str, id: str):
    """
    Toggle give up status of an element in user's list

    Parameters
    ----------
    user_id : int
        The ID of the user
    type : str
        The type of the element (movie, tv, book, books)
    id : str, int
        The ID of the element on TMDB or Booknode

    Returns
    -------
    bool
        True if the status has been toggled, False otherwise
    """
    if isinstance(id, str):
        if id.isdigit():
            id = int(id)

    ucatalog = get_ucatalog(user_id, type, id)
    catalog = get_element_by_original_id(original_id=id, type=type)
    settings = get_settings(user_id=user_id)

    if ucatalog["status"] == "giveup":
        ucatalog["status"] = get_status(
            catalog=catalog,
            ucatalog=ucatalog,
            ignore_giveup=True,
            settings=settings if settings else {},
        )
    else:
        ucatalog["status"] = "giveup"

    lexicon = default_lexicon.copy() if settings is None else settings["lexicon"]

    db.ucatalog.update_one(
        {"user_id": user_id, "type": type, "id": id},
        {"$set": {"status": ucatalog["status"]}},
    )

    text = get_ulist_text(catalog, ucatalog, lexicon)
    checked = ucatalog["status"] == "done" or ucatalog["status"] == "giveup"

    db.ulist.update_one(
        {"id": user_id, "list": {"$elemMatch": {"id": id, "type": type}}},
        {
            "$set": {
                "list.$.text": text,
                "list.$.status": ucatalog["status"],
                "list.$.checked": checked,
            }
        },
    )
    return {
        "text": text,
        "type": type,
        "id": id,
        "status": ucatalog["status"],
        "checked": checked,
    }


def set_rank(user_id: int, type: str, id: str, rank: str):
    """
    Met à jour la note d'un élément de la liste de l'utilisateur

    Parameters
    ----------
    user_id : int
        L'ID de l'utilisateur
    type : str
        Le type de l'élément (movie, tv, book, books)
    id : str, int
        L'ID de l'élément sur TMDB ou Booknode
    rank : str
        La note à assigner

    Returns
    -------
    bool
        True si la note a été mise à jour, False sinon
    """

    if isinstance(id, str):
        if id.isdigit():
            id = int(id)

    ucatalog = get_ucatalog(user_id=user_id, type=type, id=id)
    if ucatalog["exist"] is False:
        add_ulist(user_id, type, id)
        ucatalog = get_ucatalog(user_id=user_id, type=type, id=id)

    # update ucatalog
    db.ucatalog.update_one(
        {"user_id": user_id, "type": type, "id": id},
        {"$set": {"rank": rank}},
    )

    # update ulist
    catalog = db.get_collection("catalog").find_one(
        {"original_id": id, "type": type},
        {"title": 1, "type": 1, "contents": 1, "finished": 1},
    )
    ucatalog["rank"] = rank
    lexicon = get_lexicon(user_id=user_id)

    text = get_ulist_text(catalog, ucatalog, lexicon)
    checked = ucatalog["status"] == "done" or ucatalog["status"] == "giveup"

    db.ulist.update_one(
        {"id": user_id, "list": {"$elemMatch": {"id": id, "type": type}}},
        {"$set": {"list.$.text": text}},
    )
    return {
        "text": text,
        "type": type,
        "id": id,
        "status": ucatalog["status"],
        "checked": checked,
    }


def get_tierlist(user_id: int) -> dict:
    all_ucatalog = db.ucatalog.aggregate(
        [
            {"$match": {"user_id": user_id}},
            {
                "$lookup": {
                    "from": "catalog",
                    "localField": "type",
                    "foreignField": "type",
                    "as": "catalog",
                    "let": {"id": "$id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$original_id", "$$id"]}}},
                        {"$project": {"title": 1, "image": 1, "status": 1, "_id": 0}},
                    ],
                }
            },
            {"$unwind": "$catalog"},
            {
                "$project": {
                    "rank": 1,
                    "type": 1,
                    "status": 1,
                    "id": 1,
                    "catalog.title": 1,
                    "catalog.image": 1,
                }
            },
        ]
    )

    # Initialisation de la tierlist avec des catégories
    tierlist = {
        "S": [],
        "A": [],
        "B": [],
        "C": [],
        "D": [],
        "E": [],
        "F": [],
        "Unknown": [],
    }

    # Construction de la tierlist
    for ucatalog in all_ucatalog:
        query = ucatalog["rank"]
        if query == "" or query == None:
            query = "Unknown"

        tierlist[query].append(
            {
                "rank": ucatalog["rank"],
                "type": ucatalog["type"],
                "status": ucatalog["status"],
                "id": ucatalog["id"],
                "title": ucatalog["catalog"]["title"],
                "image": ucatalog["catalog"]["image"],
            }
        )

    return tierlist


def get_settings(user_id: int) -> dict:
    settings = db.settings.find_one({"user_id": user_id}, {"_id": 0})
    if settings is None:
        settings = {
            "lexicon": {},
            "adult-result": False,
            "ignore-overs": True,
        }
    if settings["lexicon"] == {}:
        settings["lexicon"] = default_lexicon.copy()
    return settings


def set_settings(user_id: int, key: str, value: bool):
    from flask import jsonify

    if db.settings.update_one({"user_id": user_id}, {"$set": {key: value}}):
        return jsonify({"status": "success", "value": value}), 200
    return jsonify({"status": "error", "value": not value}), 400


def update_user(user_id: int, data: dict):
    error = ""
    if "name" in data.keys():
        if data["name"] == "":
            error += "Nom vide, "
        elif len(data["name"]) > 30:
            error += "Nom trop long, "
        elif not db.users.update_one({"id": user_id}, {"$set": {"name": data["name"]}}):
            error += "Nom non modifié veuillez reessayer, "
    if "email" in data.keys():
        if not re.match(r"[^@]+@[^@]+\.[^@]+", data["email"]):
            error += "Email invalide, "
        elif len(data["email"]) > 50:
            error += "Email trop long, "
        elif not db.users.update_one(
            {"id": user_id}, {"$set": {"email": data["email"]}}
        ):
            error = "Email non modifié veuillez reessayer"

    if error == "":
        return {"status": "success"}
    return {"status": "error", "error": error.removesuffix(", ")}


def update_password(user_id: int, data: dict):
    user_password = db.users.find_one({"id": user_id}, {"password": 1})["password"]

    error = ""
    if "oldPassword" in data.keys():
        if data["oldPassword"] == "":
            error += "Ancien mot de passe vide, "
        elif not check_password(data["oldPassword"], user_password):
            error += "Ancien mot de passe incorrect, "
        if data["newPassword"] == "" or data["confirmPassword"] == "":
            error += "Nouveau mot de passe vide, "
        elif data["newPassword"] != data["confirmPassword"]:
            error += "Mot de passe non identique, "

    if error == "":
        db.get_collection("users").update_one(
            {"id": user_id},
            {"$set": {"password": encrypt_password(data["newPassword"])}},
        )
        return {"status": "success"}
    return {"status": "error", "error": error.removesuffix(", ")}


def set_lexicon(user_id: int, data: dict):
    db.settings.update_one({"user_id": user_id}, {"$set": {"lexicon": data}})
    return {"status": "success"}


def get_lexicon(user_id: int):
    lexicon = db.settings.find_one({"user_id": user_id}, {"lexicon": 1})["lexicon"]
    if lexicon == {}:
        lexicon = default_lexicon.copy()
    return lexicon


def save_subscription_to_db(user_id: int, subscription_data: dict):
    db.users.update_one(
        {"id": user_id}, {"$addToSet": {"subscriptions_data": subscription_data}}
    )
    return {"status": "success"}


def get_subscription_from_db(user_id: int):
    data = db.users.find_one({"id": user_id}, {"subscriptions_data": 1})
    if "subscriptions_data" in data:
        return data["subscriptions_data"]
    return None


def send_notification(user_id, title, body, url=None, icon=None):
    from pywebpush import webpush, WebPushException

    subscriptions_info = get_subscription_from_db(user_id)

    operation = []

    if subscriptions_info is None:
        print(
            f"Echec d'envoi de notification : {user_id} subscription_data n'est pas définie"
        )
        return {"status": "error"}

    for subscription_info in subscriptions_info:
        payload = json.dumps({"title": title, "body": body, "icon": icon, "url": url})

        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": "mailto:paul.a.leroy02@gmail.com"},
            )
            print(f"Notification envoyée à {user_id}, body : {body}")
        except WebPushException as ex:
            if ex.response.status_code == 410:
                operation.append(
                    UpdateOne(
                        {"id": user_id},
                        {"$pull": {"subscriptions_data": subscription_info}},
                    )
                )
            print(f"Echec d'envoi de notification : {ex}, body : {body}")

    if len(operation) > 0:
        db.users.bulk_write(operation)


def send_notification_changes(element: dict, change: dict):
    data = db.ucatalog.find(
        {"type": element["type"], "id": element["original_id"]},
        {"user_id": 1, "status": 1},
    )

    if data is None:
        return {"status": "error"}
    for user in data:
        if user["status"] != "giveup":
            if element["type"] == "tv":
                if change["change"] == "new_season":
                    title = f"{element['title']} : Nouvelle saison"
                    body = f"{change['season_title']} de la série {element['title']} est sortie !"
                else:
                    title = f"{element['title']} : Nouvelle episode"
                    body = f"L'épisode {change['episode_number']} de{'s' if change['season_number'] == 0 else ''} {change['season_title']} de la serie {element['title']} est sortie !"
            elif element["type"] == "books":
                if change["change"] == "new_book":
                    title = f"{element['title']} : Nouveau livre {change['book_index']}"
                    body = f"Le livre '{change['book_title']}' de {element['title']} ({change['books_count']}) est disponible !"
            else:
                return {"status": "error"}
            send_notification(
                user["user_id"],
                title,
                body,
                url=f"/app/{element['type']}/{element['original_id']}/",
            )
