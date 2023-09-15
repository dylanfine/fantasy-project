import requests
import json
import pandas as pd
import re
import boto3
from botocore.exceptions import ClientError
from pretty_html_table import build_table
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from io import StringIO
import urllib.parse
import datetime as dt

ENDPOINT_URL = "https://www.bovada.lv/services/sports/event/coupon/events/A/description/football/nfl-season-player-props/season-player-specials?marketFilterId=rank&preMatchOnly=true&eventsLimit=5000&lang=en"

# Faking the headers so bovada thinks its a real web traffic request
headers_string = """
Accept:
application/json, text/plain, */*
Accept-Encoding:
gzip, deflate, br
Accept-Language:
en-US,en;q=0.9
Referer:
https://www.bovada.lv/
Sec-Ch-Ua:
"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"
Sec-Ch-Ua-Mobile:
?0
Sec-Ch-Ua-Platform:
"macOS"
Sec-Fetch-Dest:
empty
Sec-Fetch-Mode:
cors
Sec-Fetch-Site:
same-origin
User-Agent:
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36
X-Channel:
desktop
X-Sport-Context:
FOOT
"""


def headers_to_json(headers_string):
    headers = {}
    lines = headers_string.strip().split("\n")
    for i in range(0, len(lines), 2):
        key = lines[i].strip()[:-1]
        value = lines[i + 1].strip()
        headers[key] = value
    return headers


def send_dataframe_as_attachment(html, df, filename="data.csv"):
    SUBJECT = "Your Daily Fantasy Magic"
    SENDER = "Fantasy Greatness <dylanjfine@gmail.com>"
    RECEIPEINTS = ["dylanjfine@gmail.com", "andrewboppart@gmail.com"]

    # Convert DataFrame to CSV string
    csv_buffer = StringIO()
    df.to_csv(csv_buffer)

    # Create a new SES client
    client = boto3.client("ses")

    # Create a multipart/mixed parent container
    msg = MIMEMultipart("mixed")
    msg["Subject"] = SUBJECT

    # Add the HTML message part
    text_part = MIMEText(html, "html")
    msg.attach(text_part)

    # Add the CSV attachment
    att = MIMEBase("application", "octet-stream")
    att.set_payload(csv_buffer.getvalue())
    encoders.encode_base64(att)
    att.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(att)

    # Send the email
    response = client.send_raw_email(
        Source=SENDER, Destinations=RECEIPEINTS, RawMessage={"Data": msg.as_string()}
    )

    return response


def extract_date(date_string):
    d = dt.datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S.%fZ")
    d = d - dt.timedelta(hours=7)
    return str(d.date())


def get_digitalsports_df():
    url = "https://bv2.digitalsportstech.com/api/game?sb=bovada&league=142"
    r = requests.get(url)
    game_ids_and_dates = [
        (provider["id"], item["date"])
        for item in r.json()
        for provider in item["providers"]
        if provider["name"] == "nix"
    ]
    lst = []
    for game_id, date in game_ids_and_dates:
        market_url = f"https://bv2.digitalsportstech.com/api/grouped-markets/v2/categories?sb=bovada&gameId={game_id}&sgmOdds=true"
        res = requests.get(market_url).json()
        over_unders = res["ou"]
        for ou_cat in over_unders:
            stat_url = f"https://bv2.digitalsportstech.com/api/dfm/marketsByOu?sb=bovada&gameId={game_id}&statistic={urllib.parse.quote(ou_cat)}"
            res = requests.get(stat_url).json()
            for player in res[0]["players"]:
                d = {}
                d["source"] = "digitalsportstech"
                d["player"] = player["name"]
                d["team"] = player["team"]
                d["game_date"] = extract_date(date)
                d["stat"] = ou_cat
                for market in player["markets"]:
                    if market["condition"] == 1:
                        d["under_line"] = market["value"]
                        d["under_odds"] = market["odds"]
                    elif market["condition"] == 3:
                        d["over_line"] = market["value"]
                        d["over_odds"] = market["odds"]
                lst.append(d)

        df = pd.DataFrame(lst)
        return df


def get_bovada_df():
    b_url = "https://www.bovada.lv/services/sports/event/coupon/events/A/description/football/nfl?lang=en"

    headers = headers_to_json(headers_string)
    d = requests.get(b_url, headers=headers)
    res = d.json()
    bovada_lst = []
    for event in res[0]["events"]:
        game_date = dt.datetime.fromtimestamp(event["startTime"] / 1000).date()
        display_groups = event["displayGroups"]
        for display_group in display_groups:
            display_group_description = display_group["description"]
            if display_group_description not in [
                "Receiving Props",
                "QB Props",
                "Rushing Props",
            ]:
                continue
            for market in display_group["markets"]:
                market_description = market["description"]
                stat = market_description.split("-")[0].strip()
                player = market_description.split("-")[1].strip()

                d = {}
                d["source"] = "bovada"
                d["game_date"] = str(game_date)
                d["player"] = player
                d["stat"] = stat
                for outcome in market["outcomes"]:
                    if outcome["description"] == "Over":
                        d["over_line"] = outcome["price"]["handicap"]
                        d["over_odds"] = outcome["price"]["decimal"]
                    elif outcome["description"] == "Under":
                        d["under_line"] = outcome["price"]["handicap"]
                        d["under_odds"] = outcome["price"]["decimal"]
                bovada_lst.append(d)
    bovada_df = pd.DataFrame(bovada_lst)
    return bovada_df


def lambda_handler(event, context):
    ds_df = get_digitalsports_df()
    bovada_df = get_bovada_df()

    df = pd.concat([ds_df, bovada_df], ignore_index=True)

    html = f"""<body><h1>See fantasy data below!!</h1></body>""" + build_table(
        df, color="green_light"
    )
    send_dataframe_as_attachment(html, df)
