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

ENDPOINT_URL = 'https://www.bovada.lv/services/sports/event/coupon/events/A/description/football/nfl-season-player-props/season-player-specials?marketFilterId=rank&preMatchOnly=true&eventsLimit=5000&lang=en'

#Faking the headers so bovada thinks its a real web traffic request
headers_string = '''
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
''' 

def headers_to_json(headers_string):
    headers = {}
    lines = headers_string.strip().split("\n")
    for i in range(0, len(lines), 2):
        key = lines[i].strip()[:-1]
        value = lines[i+1].strip()
        headers[key] = value
    return headers

def extract_decimal(s: str) -> float:
    match = re.search(r"(\d+\.\d+)", s)
    if match:
        return float(match.group(1))
    return None


def extract_player_stat(line: str) -> tuple:
    
    # Regular expression to match lines that contain player names and stats
    pattern = r'^(?P<name>[A-Za-z. ]+) (?P<year>\d{4}-\d{2}) Regular Season Total (?P<stat>.+)$'

    match = re.match(pattern, line)
    if match:
        return match.group('name'), match.group('stat')
    return None

def send_dataframe_as_attachment(html,df, filename="data.csv"):
    SUBJECT =  "Your Daily Fantasy Magic"
    SENDER = "Fantasy Greatness <dylanjfine@gmail.com>"
    RECEIPEINTS = ['dylanjfine@gmail.com','andrewboppart@gmail.com']

    # Convert DataFrame to CSV string
    csv_buffer = StringIO()
    df.to_csv(csv_buffer)

    # Create a new SES client
    client = boto3.client('ses')

    # Create a multipart/mixed parent container
    msg = MIMEMultipart('mixed')
    msg['Subject'] = SUBJECT

    # Add the HTML message part
    text_part = MIMEText(html, 'html')
    msg.attach(text_part)

    # Add the CSV attachment
    att = MIMEBase('application', 'octet-stream')
    att.set_payload(csv_buffer.getvalue())
    encoders.encode_base64(att)
    att.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(att)

    # Send the email
    response = client.send_raw_email(
        Source=SENDER,
        Destinations=RECEIPEINTS,
        RawMessage={'Data': msg.as_string()}
    )
    
    return response

def lambda_handler(event,context):
    headers = headers_to_json(headers_string)
    data = requests.get(ENDPOINT_URL,headers=headers).json()

    lst = []
    for event in data[0]['events']:
        markets = event ['displayGroups'][0]['markets']
        for market in markets:
            market_description = market['description']
            outcomes = market['outcomes']
            
            if "Sacks" in market_description or "Tackles" in market_description:
                continue
            elif '2023-24 To' in market_description:
                d = {}
                d['stat'] = market_description.replace('2023-24 To','').strip()
                for outcome in outcomes:
                    d['player_name'] = outcome['description']
                    d['odds'] = outcome['price']['american']
                    lst.append(d.copy())
            else:   
                d = {}
                play_stat_tup = extract_player_stat(market_description)
                if not play_stat_tup:
                    continue
                name,stat = play_stat_tup
                d['player_name'] = name
                d['stat'] = stat
                for outcome in outcomes:
                    outcome_description = outcome['description']
                    if 'Over' in outcome_description:
                        d['line'] = extract_decimal(outcome_description)
                        d['odds'] = outcome['price']['american']
                lst.append(d)

    df = pd.DataFrame(lst)

    html = (
        f"""<body><h1>See fantasy data below!!</h1></body>"""
        + build_table(df, color="green_light")
    )
    send_dataframe_as_attachment(html,df)
