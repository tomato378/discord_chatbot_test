import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

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

@bot.event
async def on_message(message):
    # ボット自身のメッセージは無視
    if message.author == bot.user:
        return

    # 特定の文字列に反応
    if 'こんにちは' in message.content:
        await message.channel.send('こんにちは！')
    elif 'おはよう' in message.content:
        await message.channel.send('おはようございます！')
    elif '疲れた' in message.content:
        await message.channel.send('お疲れ様です！')

    # コマンドの処理を可能にする
    await bot.process_commands(message)

# 環境変数からトークンを取得して実行
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    print('エラー: .envファイルにDISCORD_TOKENが設定されていません')
else:
    bot.run(TOKEN)
