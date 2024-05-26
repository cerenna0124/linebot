from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *

#======python的函數庫==========
import tempfile, os
import datetime
import time
import requests
#======python的函數庫==========

app = Flask(__name__)
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')
# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))
# Notion tokenn
notion_token=os.getenv('NOTION_TOKEN')
# Notion Database id
database_id=os.getenv('NOTION_DATABASE_ID')

#Notion Command
headers = {
    "Authorization": "Bearer " + notion_token,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

def get_pages(num_pages=None):
    """
    If num_pages is None, get all pages, otherwise just the defined number.
    """
    url = f"https://api.notion.com/v1/databases/{database_id}/query"

    get_all = num_pages is None
    page_size = 100 if get_all else num_pages

    payload = {"page_size": page_size}
    response = requests.post(url, json=payload, headers=headers)

    data = response.json()

    results = data["results"]
    while data["has_more"] and get_all:
        payload = {"page_size": page_size, "start_cursor": data["next_cursor"]}
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        results.extend(data["results"])

    return results

def insert_data(msg:str):
    url = "https://api.notion.com/v1/pages"
    dt=datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')
    data = {
    'Message': {'title': [{'text': {'content': msg}}]},
    'Date': {'rich_text': [{'text': {'content': dt}}]}}
    payload = {"parent": {"database_id": database_id}, "properties": data}
    res = requests.post(url, headers=headers, json=payload)
    return res
    
def delete_data():
    payload = {"archived": True}
    all_pages=get_pages()
    deleted_row=0
    for each_id in all_pages:
        url = f"https://api.notion.com/v1/pages/{each_id['id']}"
        res = requests.patch(url, json=payload, headers=headers)
        if res.status_code==200:
            deleted_row+=1
    return f'{deleted_row} records was deleted'
    
# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


# 處理訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    insert_data(msg)
    if msg=='@對話紀錄':
        datas=get_pages()
        text_list=[]
        for each in datas:
            msg=each['properties']['Message']['title'][0]['plain_text']
            dt=each['properties']['Date']['rich_text'][0]['plain_text']
          if '@' not in msg:
            text_list.append(msg+'  |  '+dt)
        data_text = '\n'.join(text_list)
        message = TextSendMessage(text=data_text)

    elif msg=='@刪除':
        data=len(get_pages())
        delete_data()
        message = TextSendMessage(text=f'{data} records was deleted')

    elif msg=='@功能':
        message = TextSendMessage(text='@對話紀錄: 顯示所有對話紀錄\n@刪除: 刪除所有對話紀錄')

    else:
        message = TextSendMessage(text=f'{msg} already save in Notion')
        
    line_bot_api.reply_message(event.reply_token, message)

@handler.add(PostbackEvent)
def handle_message(event):
    print(event.postback.data)


@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name}歡迎加入')
    line_bot_api.reply_message(event.reply_token, message)
        
        
import os
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
