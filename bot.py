import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import re
import asyncio
from datetime import datetime, timedelta
import pytz  # 追加
from google.oauth2 import service_account
from googleapiclient.discovery import build
from typing import Dict

# 環境変数を読み込む
load_dotenv()

# インテントを設定
intents = discord.Intents.default()
intents.message_content = True  # メッセージの内容を読み取る権限
intents.members = True          # メンバー情報を読み取る権限
intents.guilds = True          # サーバー情報を読み取る権限

# ボットのプレフィックスを設定（コマンドの前につける記号）
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} としてログインしました')
    print('------------------------')
    print(f'導入サーバー数: {len(bot.guilds)}')
    print('起動完了')

@bot.command()
async def hello(ctx):
    await ctx.send('こんにちは！')

# Google Calendar 設定
GOOGLE_SA_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
CALENDAR_ID = os.getenv('CALENDAR_ID')

_calendar_service = None
if GOOGLE_SA_FILE and CALENDAR_ID:
    try:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_SA_FILE,
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        _calendar_service = build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f'Google Calendar 初期化エラー: {e}')

def _make_event_payload(start_dt: datetime, end_dt: datetime, title: str, description: str):
    return {
        'summary': title,
        'description': description,
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'Asia/Tokyo'
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': 'Asia/Tokyo'
        }
    }

def _create_event_sync(start_dt: datetime, end_dt: datetime, title: str, description: str):
    if _calendar_service is None:
        raise RuntimeError('Calendar service is not configured')
    body = _make_event_payload(start_dt, end_dt, title, description)
    event = _calendar_service.events().insert(calendarId=CALENDAR_ID, body=body).execute()
    return event

# ユーザーの予定作成状態を保持する辞書
scheduling_states: Dict[int, Dict] = {}

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.strip()
    user_id = message.author.id

    # 予定作成の状態確認
    if user_id in scheduling_states:
        state = scheduling_states[user_id]
        
        if state['step'] == 'date':
            if not re.match(r'^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$', content):
                await message.channel.send('日付の形式が正しくありません。YYYY-MM-DD の形式で入力してください。\n例: 2025-10-25')
                return
            state['date'] = content
            state['step'] = 'time'
            await message.channel.send('時刻を入力してください（HH:MM）\n例: 15:00')
            return
            
        elif state['step'] == 'time':
            if not re.match(r'^(?:[01]\d|2[0-3]):[0-5]\d$', content):
                await message.channel.send('時刻の形式が正しくありません。HH:MM の形式で入力してください。\n例: 15:00')
                return
            state['time'] = content
            state['step'] = 'duration'
            await message.channel.send('予定の長さを分単位で入力してください（1-1440）\n例: 60')
            return
            
        elif state['step'] == 'duration':
            try:
                duration = int(content)
                if duration <= 0 or duration > 1440:
                    raise ValueError()
                state['duration'] = duration
                state['step'] = 'title'
                await message.channel.send('予定のタイトルを入力してください')
                return
            except ValueError:
                await message.channel.send('1から1440までの数字を入力してください')
                return
                
        elif state['step'] == 'title':
            state['title'] = content
            state['step'] = 'description'
            await message.channel.send('予定の説明を入力してください（省略する場合は「なし」と入力）')
            return
            
        elif state['step'] == 'description':
            description = '' if content.lower() == 'なし' else content
            
            # 予定をカレンダーに追加
            try:
                jst = pytz.timezone('Asia/Tokyo')
                start = datetime.strptime(f"{state['date']} {state['time']}", "%Y-%m-%d %H:%M")
                start = jst.localize(start)
                end = start + timedelta(minutes=state['duration'])
                
                event = await asyncio.to_thread(_create_event_sync, start, end, state['title'], description)
                link = event.get('htmlLink')
                await message.channel.send(f'予定を追加しました！\n'
                                         f'タイトル: {state["title"]}\n'
                                         f'日時: {state["date"]} {state["time"]}\n'
                                         f'長さ: {state["duration"]}分\n'
                                         f'リンク: {link}')
                
            except Exception as e:
                await message.channel.send(f'予定の作成に失敗しました: {e}')
            
            # 状態をクリア
            del scheduling_states[user_id]
            return

    # 予定追加の開始
    if content == '予定追加':
        scheduling_states[user_id] = {
            'step': 'date',
        }
        await message.channel.send('予定を追加します。\n日付を入力してください（YYYY-MM-DD）\n例: 2025-10-25')
        return

    # カレンダー予定追加のフォーマットチェック
    m = re.match(r'^\s*cal:\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s*\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.*)$', content, re.IGNORECASE)
    if m:
        if _calendar_service is None:
            await message.channel.send('カレンダーが未設定です。管理者に連絡してください。')
        else:
            date_str, time_str, duration_min, title, description = m.groups()
            try:
                # 日付と時刻のフォーマットを検証
                if not re.match(r'^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$', date_str):
                    raise ValueError('日付の形式が不正です')
                if not re.match(r'^(?:[01]\d|2[0-3]):[0-5]\d$', time_str):
                    raise ValueError('時刻の形式が不正です')
                
                # 日時をパース
                jst = pytz.timezone('Asia/Tokyo')  # 変更
                start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                start = jst.localize(start)  # 変更
                
                # 継続時間のチェック
                duration = int(duration_min)
                if duration <= 0 or duration > 1440:  # 24時間以内
                    raise ValueError('継続時間は1分以上24時間以内で指定してください')
                
                end = start + timedelta(minutes=duration)
                
                # デバッグ情報を出力
                print(f"パース結果: start={start}, end={end}, duration={duration}分")
                
            except ValueError as ve:
                await message.channel.send(f'エラー: {str(ve)}\n正しい形式: cal: 2025-10-25 15:00 | 60 | 会議 | 説明')
            except Exception as e:
                await message.channel.send(f'予期せぬエラー: {str(e)}\n正しい形式: cal: 2025-10-25 15:00 | 60 | 会議 | 説明')
            else:
                try:
                    event = await asyncio.to_thread(_create_event_sync, start, end, title, description)
                    link = event.get('htmlLink')
                    await message.channel.send(f'予定を追加しました: {title}\n{link}')
                except Exception as e:
                    await message.channel.send(f'予定の作成に失敗しました: {e}')

    # 既存のキーワード応答
    if '予定' in content:
        await message.channel.send('cal: 2025-10-25 15:00 | 60 | ミーティング | プロジェクトの進捗確認')
    elif 'おはよう' in content:
        await message.channel.send('おはようございます！')
    elif '疲れた' in content:
        await message.channel.send('お疲れ様です！')

    await bot.process_commands(message)

# 環境変数からトークンを取得して実行
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    print('エラー: .envファイルにDISCORD_TOKENが設定されていません')
else:
    bot.run(TOKEN)
