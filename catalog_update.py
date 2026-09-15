import os

if os.getenv("ENV") != "production":
    print("Development environment")
    from dotenv import load_dotenv

    load_dotenv()


import api
from datetime import date, timedelta
from pymongo import UpdateOne
import requests

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def _send_discord_error(message: str):
    """Envoie une notification d'erreur sur Discord via webhook."""
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": f"[catalog_update] {message}"},
            timeout=10,
        )
    except Exception:
        pass


def process_update(element, new_data, extra_fields=None):
    """Fonction utilitaire pour créer une mise à jour MongoDB."""
    update_data = {
        "title": new_data.get("title", new_data.get("name")),
        "overview": new_data["overview"],
        "image": new_data["image"],
        "last_update": date.today().isoformat(),
        "recommandate_update": api.get_recommandate_date(new_data, element["type"]),
    }
    if extra_fields:
        update_data.update(extra_fields)

    return UpdateOne(
        {"id": element["id"], "type": element["type"]}, {"$set": update_data}
    )


def update_tv_seasons(element: dict, operation: list):
    """Gère la mise à jour des saisons pour les séries TV."""
    finished = True

    new_data = {"contents": [], "finished": True}

    have_notification = False

    for content in element["contents"]:
        new_season_data = None
        if date.today() >= date.fromisoformat(content["recommandate_update"]):
            print(
                f"Check Update {element['title']} {content['title']} recommandé le {content['recommandate_update']}"
            )
            try:
                new_season_data = api.get_info_about_season(
                    element["original_id"], content["season_number"]
                )
            except:
                continue
            operation.append(
                UpdateOne(
                    {
                        "id": element["id"],
                        "type": element["type"],
                        "contents": {
                            "$elemMatch": {"season_number": content["season_number"]}
                        },
                    },
                    {"$set": {"contents.$": new_season_data}},
                )
            )
            if (
                content["contents"] != new_season_data["contents"]
                and not have_notification
            ):
                for j, episode in enumerate(new_season_data["contents"]):
                    if len(content["contents"]) < j + 1:
                        api.send_notification_changes(
                            element,
                            {
                                "change": "new_episode",
                                "season_number": content["season_number"],
                                "season_title": content["title"],
                                "episode_number": j + 1,
                            },
                        )

                        have_notification = True
                        break

        new_data["contents"].append(new_season_data if new_season_data else content)

        if not content.get("finished", True):
            finished = False

    if finished != element.get("finished", True):
        operation.append(
            UpdateOne(
                {"id": element["id"], "type": element["type"]},
                {"$set": {"finished": finished}},
            )
        )

    new_data["finished"] = finished

    return new_data


def _process_element(element, today, operation):
    """Traite un seul élément du catalogue et retourne True si une notification doit être envoyée."""
    have_change = False

    if today >= date.fromisoformat(element["recommandate_update"]):
        print(
            f"Check Update {element['type']}, {element['original_id']}, {element['title']} recommandé le {element['recommandate_update']}"
        )
        if element["type"] == "book":
            new_data = api.get_book_by_id(element["original_id"])

            operation.append(process_update(element, new_data))

        elif element["type"] == "movie":
            new_data = api.get_movie_by_id(element["original_id"])

            operation.append(process_update(element, new_data))

        elif element["type"] == "books":
            new_data = api.get_books_by_id(element["original_id"])
            operation.append(
                process_update(
                    element,
                    new_data,
                    extra_fields={"contents": new_data["contents"]},
                )
            )
            if len(new_data["contents"][0]["contents"]) != len(
                element["contents"][0]["contents"]
            ):
                for j, book in enumerate(new_data["contents"][0]["contents"]):
                    if len(element["contents"][0]["contents"]) < j + 1:
                        api.send_notification_changes(
                            element,
                            {
                                "change": "new_book",
                                "book_title": book,
                                "book_index": j + 1,
                                "books_count": len(
                                    new_data["contents"][0]["contents"]
                                ),
                            },
                        )

                        have_change = True

            if have_change:
                element["contents"] = new_data["contents"]

        elif element["type"] == "tv":
            new_data = api.get_tv_by_id(element["original_id"])

            contents: list[dict] = new_data["contents"]
            finished = all([content.get("finished", True) for content in contents])
            operation.append(
                process_update(
                    element,
                    new_data,
                    extra_fields={
                        "contents": contents,
                        "finished": finished,
                        "recommandate_update": (
                            today + timedelta(days=30)
                        ).isoformat(),
                    },
                )
            )

            if len(contents) != len(element["contents"]):
                for i, content in enumerate(contents):
                    econtents = next(
                        (
                            c
                            for c in element["contents"]
                            if str(c["season_number"])
                            == str(content["season_number"])
                        ),
                        None,
                    )

                    if not econtents:
                        api.send_notification_changes(
                            element,
                            {
                                "change": "new_season",
                                "season_number": content["season_number"],
                                "season_title": content["title"],
                            },
                        )

                        have_change = True
                        break
            else:
                for i, content in enumerate(contents):
                    if content["contents"] != element["contents"][i]["contents"]:
                        have_to_break = False
                        for j, episode in enumerate(content["contents"]):
                            if len(element["contents"][i]["contents"]) < j + 1:
                                api.send_notification_changes(
                                    element,
                                    {
                                        "change": "new_episode",
                                        "season_number": content["season_number"],
                                        "season_title": content["title"],
                                        "episode_number": j + 1,
                                    },
                                )
                                have_change = True
                                have_to_break = True
                                break
                        if have_to_break:
                            break

            if have_change:
                element["contents"] = contents

    else:
        if element["type"] == "tv":
            new_data = update_tv_seasons(element, operation)

            if new_data["contents"] != element["contents"]:
                have_change = True
                element["contents"] = new_data["contents"]

            if new_data["finished"] != element["finished"]:
                have_change = True
                element["finished"] = new_data["finished"]

    return have_change


def check_update_catalog():
    today = date.today()

    data = api.db.get_collection("catalog").find(
        {},
        {
            "id": 1,
            "type": 1,
            "original_id": 1,
            "recommandate_update": 1,
            "contents": 1,
            "finished": 1,
            "title": 1,
        },
    )

    operation = []

    for element in data:
        try:
            have_change = _process_element(element, today, operation)

            if have_change is True:
                for ucatalog in api.db.ucatalog.find(
                    {"id": element["original_id"], "type": element["type"]}
                ):
                    api.send_update_ucatalog(element, ucatalog)
        except Exception as e:
            message = (
                f"Erreur lors du traitement de {element['type']} {element['title']} "
                f"(id={element['original_id']}): {e}"
            )
            print(message)
            _send_discord_error(message)

    if operation:
        api.db.catalog.bulk_write(operation)


check_update_catalog()
