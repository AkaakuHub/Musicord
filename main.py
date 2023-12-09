import os
import re
import glob
import time
import datetime
import math
import shutil
import asyncio
import json
import random
import discord
import subprocess
from discord.ext import commands
from discord.ui import Select, View
from discord import app_commands

PREFIX = os.getenv("PREFIX")
ACTIVITY = os.getenv("ACTIVITY")
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
IS_LOCAL = os.getenv("IS_LOCAL")

intents = discord.Intents.all()
intents.typing = False
intents.presences = False
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

os.environ["TZ"] = "Asia/Tokyo"

# manual
with open("data/manual.json", "r", encoding="utf-8") as json_file:
    man_data = json.load(json_file)

# memberごとにデータを保存する
with open("data/member.json", "r", encoding="utf-8") as json_file:
    member_data = json.load(json_file)

# サーバーIDをリストにして保存
guild_ids = [int(id_str) for id_str in member_data]

#########


@client.event
async def on_ready():
    print("起動しました!")
    activity = discord.Game(name=ACTIVITY)
    await client.change_presence(activity=activity)
    await slash_register()


async def slash_register():
    try:
        for guild_id in guild_ids:
            await tree.sync(guild=discord.Object(id=guild_id))
        print("slash command synced")
    except Exception as e:
        print(e)


# member_dataにもしidがいなかったらお知らせする
async def check_every(interaction):
    if str(interaction.user.id) not in member_data[str(interaction.guild.id)]:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("どうやらあなたはまだ何も発言していないようです。\nまずはなにか挨拶をしてみましょう！。")
        print(f"{interaction.user.id}はmember_dataに登録されていません")
        return False
    else:
        return True

######

# 次の曲に自動で移る
async def play_next(guild_id):
    # 再生待ちがあるなら、再生
    if len(member_data[str(guild_id)]["data"]["queue"]) != 0:
        print("play_next\n")
        
        music_name = member_data[str(guild_id)]["data"]["queue"][0]
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(f"music/{music_name}"), volume=0.5)
        
        # queueから削除
        member_data[str(guild_id)]["data"]["queue"].pop(0)
        
        print(member_data[str(guild_id)]["data"])
        
        client.get_guild(guild_id).voice_client.play(source, after = lambda _: asyncio.run_coroutine_threadsafe(play_next(guild_id), client.loop))
    else:
        print("play_ended\n")
        member_data[str(guild_id)]["data"]["is_playing"] = "False"
        print(member_data[str(guild_id)]["data"])
        return None

@client.event
async def on_message(message):
    global wordle_running, member_data
    # 書き換えるのにglobal必要
    if message.author == client.user:
        return

    # 新たなメンバーがいたら登録する、名前が変わったら更新する
    # 要注意！！message.author.id は int型、jsonファイルのmember_dataを検索するときの、keyはstr型、python側では関係ない
    # サーバー(非DM)のときのみdata/member.jsonを更新する
    if message.guild:
        guild_id = str(message.guild.id)
        if guild_id not in member_data:
            new_data = {}
            member_data[guild_id] = new_data

            with open("data/member.json", "w", encoding="utf-8") as json_file:
                json.dump(member_data, json_file, ensure_ascii=False, indent=4)
            with open("data/member.json", "r", encoding="utf-8") as json_file:
                member_data = json.load(json_file)

            print(message.guild.id, "サーバーを登録しました")

        if str(message.author.id) not in member_data[guild_id]:
            new_data = {
            }
            member_data[guild_id][message.author.id] = new_data

            with open("data/member.json", "w", encoding="utf-8") as json_file:
                json.dump(member_data, json_file, ensure_ascii=False, indent=4)
            with open("data/member.json", "r", encoding="utf-8") as json_file:
                member_data = json.load(json_file)
            print(message.author.id, message.author.name, "を新たに登録しました")
        elif (
            message.author.name != member_data[guild_id][str(message.author.id)]["name"]
        ):
            member_data[guild_id][str(message.author.id)]["name"] = message.author.name

            with open("data/member.json", "w", encoding="utf-8") as json_file:
                json.dump(member_data, json_file, ensure_ascii=False, indent=4)
            with open("data/member.json", "r", encoding="utf-8") as json_file:
                member_data = json.load(json_file)
            print(message.author.id, message.author.name, "の名前を更新しました")

    # 常に発動するコマンド
    if message.content == "connect":
        if message.author.voice is None:
            await message.channel.send("あなたはボイスチャンネルに接続していません。")
            return
        
        await message.author.voice.channel.connect()
        await message.channel.send("接続しました。")
        # ボイスチャンネルのidを、辞書に記録しておく
        member_data[str(message.guild.id)]["data"]["voice_channel_id"] = message.author.voice.channel.id
        # queueを初期化
        member_data[str(message.guild.id)]["data"]["queue"] = []
        # is_playingをfalseに
        member_data[str(message.guild.id)]["data"]["is_playing"] = "False"
        print(member_data[str(message.guild.id)]["data"])
        
    if message.content == "leave":
        if message.guild.voice_client is None:
            await message.channel.send("ボイスチャンネルに接続していません。")
            return
        
        await message.guild.voice_client.disconnect()
        await message.channel.send("切断しました。")
        # 辞書から削除
        member_data[str(message.guild.id)]["data"]["voice_channel_id"] = ""
        # queueを初期化
        member_data[str(message.guild.id)]["data"]["queue"] = []
        # is_playingをfalseに
        member_data[str(message.guild.id)]["data"]["is_playing"] = "False"
        print(member_data[str(message.guild.id)]["data"])
    
    if message.content == "queue":
        if message.guild.voice_client is None:
            await message.channel.send("ボイスチャンネルに接続していません。")
            return
        
        if len(member_data[str(message.guild.id)]["data"]["queue"]) == 0:
            await message.channel.send("再生待ちの曲がありません。")
            return
        
        queue = ""
        for music in member_data[str(message.guild.id)]["data"]["queue"]:
            queue += f"{music.split('_a')[0]}\n"
        await message.channel.send(queue)
        
    if message.content == "pause":
        if message.guild.voice_client is None:
            await message.channel.send("ボイスチャンネルに接続していません。")
            return
        
        message.guild.voice_client.pause()
        
    if message.content == "resume":
        if message.guild.voice_client is None:
            await message.channel.send("ボイスチャンネルに接続していません。")
            return
        
        message.guild.voice_client.resume()
        
    if message.content == "stop":
        if message.guild.voice_client is None:
            await message.channel.send("ボイスチャンネルに接続していません。")
            return
        
        message.guild.voice_client.stop()
        
    if message.content == "skip":
        if message.guild.voice_client is None:
            await message.channel.send("ボイスチャンネルに接続していません。")
            return
        
        if len(member_data[str(message.guild.id)]["data"]["queue"]) == 0:
            await message.channel.send("再生待ちの曲がありません。")
            return
        
        # 再生中なら、一度stopしてから再生
        is_playing = member_data[str(message.guild.id)]["data"]["is_playing"]
        if is_playing == "True":
            message.guild.voice_client.stop()

        member_data[str(message.guild.id)]["data"]["queue"].pop(0)
        
        next_music = member_data[str(message.guild.id)]["data"]["queue"][0]
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(f"music/{next_music}"), volume=0.5)
        message.guild.voice_client.play(source)
        
    # if "volume" in message.content: # volume 0.5
    #     if message.guild.voice_client is None:
    #         await message.channel.send("ボイスチャンネルに接続していません。")
    #         return
        
    #     vol = float(message.content.split()[1]) # 0-1のみ、ほかはreturn
    #     if vol < 0 or vol > 1:
    #         await message.channel.send("0から1の間で指定してください。")
    #         return
    #     source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio("test.mp3"), volume=vol)
    #     # このままだと、すでに再生中なので、一度stopする
    #     message.guild.voice_client.stop()
    #     message.guild.voice_client.play(source)
        
    if message.content.startswith("http"):
        if message.guild.voice_client is None:
            await message.channel.send("ボイスチャンネルに接続していません。")
            return
        
        service = "none"
        url = ""
        
        # https://youtu.be/-rrxUPDS-l0?si=E7I6tTMw6jffqejM => -rrxUPDS-l0
        if "youtu.be" in message.content:
            # id = message.content.split("/")[-1].split("?")[0]
            service = "youtube"
            url = message.content
        
        # https://m.youtube.com/watch?v=-rrxUPDS-l0 => -rrxUPDS-l0
        # https://www.youtube.com/watch?v=-rrxUPDS-l0 => -rrxUPDS-l0
        if "m.youtube.com" in message.content or "www.youtube.com" in message.content:
            # id = message.content.split("=")[-1]
            service = "youtube"
            url = message.content

        if service != "none":
            print(service, id)
            # yt-dlpでダウンロード
            if service == "youtube":
                if IS_LOCAL == "True":
                    command = f'yt-dlp -f 251/250/249/600 -o "music\\%(title)s_a.%(ext)s" --no-mtime {url}'
                else:
                    command = f'yt-dlp -f 251/250/249/600 -o "music/%(title)s_a.%(ext)s" --no-mtime {url}'

            # 現時点でのmusicフォルダ内を、リストで取得
            music_list = glob.glob(os.path.join(os.getcwd(), "music", "*"))
            status = await run_command("ytdlp_a", command)
            if status == "200":
                # musicフォルダ内の差分を取得
                new_music_list = glob.glob(os.path.join(os.getcwd(), "music", "*"))
                new_music = list(set(new_music_list) - set(music_list))
                # plsylistに追加 今は1つだけ
                # パスではなく、ファイル名と拡張子のみ
                if IS_LOCAL == "True":
                    new_music_name = new_music[0].split("\\")[-1]
                else:
                    new_music_name = new_music[0].split("/")[-1]
                    
                    
                member_data[str(message.guild.id)]["data"]["queue"].append(new_music_name)
                
                # is_playingがfalseなら、今すぐに再生
                is_playing = member_data[str(message.guild.id)]["data"]["is_playing"]
                
                if is_playing == "False":
                    member_data[str(message.guild.id)]["data"]["is_playing"] = "True"
                    
                    music_name = member_data[str(message.guild.id)]["data"]["queue"][0]
                    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(f"music/{music_name}"), volume=0.5)
                    
                    # queueから削除
                    member_data[str(guild_id)]["data"]["queue"].pop(0)
                    
                    loop = asyncio.get_event_loop()
                    message.guild.voice_client.play(source, after = lambda _: loop.create_task(play_next(message.guild.id)))
                    
                else:
                    print(member_data[str(guild_id)]["data"])
                    await message.channel.send("再生待ちに追加しました。")
            else:
                await message.channel.send("エラーが発生しました。")
                return

##別でコマンド実行系###
async def run_command(kind, command):
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()
        print("STDOUT:", stdout)
        print("STDERR:", stderr)

        if kind == "ytdlp_a":
            return "200"
        else:
            return None
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.output}\n")

# そのうち応用するかも
# async def delete_data(interaction, keyword):
#     try:
#         file_list = glob.glob(os.path.join(os.getcwd(), f"*{keyword}*"))
#         if not file_list:
#             print("削除対象のファイルが見つかりませんでした。")
#             await interaction.followup.send("エラー5")

#         for file_to_remove in file_list:
#             try:
#                 os.remove(file_to_remove)
#                 print(f"正常に削除: {file_to_remove}")
#             except Exception as e:
#                 print(f"ファイルの削除中にエラーが発生しました: {e}")
#                 await interaction.followup.send("エラー6")
#     except TimeoutError as e:
#         print(f"TimeOutError: {e}")
#         await interaction.followup.send("タイムアウト")
#         return None
#     except Exception as e:
#         print(f"エラーが発生しました: {e}")
#         await interaction.followup.send("エラー7")


#### これより上にコマンドを追加していく####
if not TOKEN:
    print("DISCORD_BOT_TOKENが設定されていません")

if IS_LOCAL == "True":
    client.run(TOKEN)
else:
    # replitよう
    from keep_alive import keep_alive  # automation

    ###
    # automation
    keep_alive()
    try:
        client.run(TOKEN)
    except:
        os.system("kill 1")
