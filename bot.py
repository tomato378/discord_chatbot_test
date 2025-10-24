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

# ボットのプレフィックスを設定（コマンドの前につける記号）
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} としてログインしました')
    print('------------------------')
    print('起動完了')

@bot.command()
async def hello(ctx):
    await ctx.send('こんにちは！')

# 環境変数からトークンを取得して実行
bot.run(os.getenv('DISCORD_TOKEN'))
