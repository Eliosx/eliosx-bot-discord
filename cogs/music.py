import discord
from discord.ext import commands
import yt_dlp
import asyncio
from collections import deque
import os
import random
import logging
import platform

from utils.helpers import ydl_opts, ffmpeg_options, PaginationView

logging.getLogger('discord.player').setLevel(logging.ERROR)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.is_processing = {}
        self.now_playing_msgs = {}
        self.autoplay_estado = {}
        self.last_played = {}

    def check_queue(self, ctx):
        if self.queues.get(ctx.guild.id):
            if not ctx.voice_client or not ctx.voice_client.is_connected():
                self.is_processing[ctx.guild.id] = False
                return
            search_data = self.queues[ctx.guild.id].popleft()
            self.is_processing[ctx.guild.id] = True 
            asyncio.run_coroutine_threadsafe(self.safe_play(ctx, search_data), self.bot.loop)
        elif self.autoplay_estado.get(ctx.guild.id, False) and ctx.guild.id in self.last_played:
            self.is_processing[ctx.guild.id] = True
            asyncio.run_coroutine_threadsafe(self.do_autoplay(ctx), self.bot.loop)
        else:
            self.is_processing[ctx.guild.id] = False
            if ctx.voice_client and ctx.voice_client.is_connected():
                asyncio.run_coroutine_threadsafe(ctx.send("🎵 Cola finalizada."), self.bot.loop)

    async def safe_play(self, ctx, search_data):
        await asyncio.sleep(1)
        await self.play_music(ctx, search_data['url'])

    async def do_autoplay(self, ctx):
        last_id = self.last_played.get(ctx.guild.id)
        mix_url = f"https://www.youtube.com/watch?v={last_id}&list=RD{last_id}"
        loop = asyncio.get_event_loop()
        
        fast_opts = {'extract_flat': True, 'quiet': True, 'playlist_items': '1-10'} 
        
        with yt_dlp.YoutubeDL(fast_opts) as ydl:
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(mix_url, download=False))
        
        if 'entries' in data:
            for entry in data['entries']:
                if entry and entry.get('id') != last_id:
                    url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                    return await self.safe_play(ctx, {'url': url})
                    
        self.is_processing[ctx.guild.id] = False
        await ctx.send("🎵 No hay recomendaciones diferentes disponibles.")

    async def play_music(self, ctx, search_url):
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(search_url, download=False))
            
            if 'entries' in data:
                data = data['entries'][0]

            if not ctx.voice_client or not ctx.voice_client.is_connected():
                return
            
            self.last_played[ctx.guild.id] = data['id']
            source = await discord.FFmpegOpusAudio.from_probe(data['url'], **ffmpeg_options)
            
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()

            ctx.voice_client.play(source, after=lambda e: self.check_queue(ctx))
            
            embed = discord.Embed(title=data['title'], url=data.get('webpage_url', search_url), color=discord.Color.blue())
            embed.set_footer(text="Reproduciendo ahora")
            
            if ctx.guild.id in self.now_playing_msgs:
                old_msg = self.now_playing_msgs[ctx.guild.id]
                try:
                    if ctx.channel.last_message_id == old_msg.id:
                        await old_msg.edit(embed=embed)
                    else:
                        await old_msg.delete()
                        self.now_playing_msgs[ctx.guild.id] = await ctx.send(embed=embed)
                except discord.NotFound:
                    self.now_playing_msgs[ctx.guild.id] = await ctx.send(embed=embed)
            else:
                self.now_playing_msgs[ctx.guild.id] = await ctx.send(embed=embed)
            
        except Exception as e:
            if ctx.voice_client and ctx.voice_client.is_connected():
                await ctx.send("⚠️ Error con una canción, saltando...")
                self.check_queue(ctx)
        finally:
            self.is_processing[ctx.guild.id] = False

    async def background_load(self, ctx, remaining_entries, should_shuffle=True):
        for entry in remaining_entries:
            url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
            self.queues[ctx.guild.id].append({'titulo': entry.get('title', 'Video desconocido'), 'url': url})

        if should_shuffle and len(self.queues[ctx.guild.id]) > 1:
            lista_aux = list(self.queues[ctx.guild.id])
            random.shuffle(lista_aux)
            self.queues[ctx.guild.id] = deque(lista_aux)
            await ctx.send("🔀 **Cola mezclada automáticamente.**")

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, search: str):
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        if ctx.guild.id not in self.queues:
            self.queues[ctx.guild.id] = deque()
        if not search.startswith("http"):
            search = f"ytsearch:{search}"

        async with ctx.typing():
            fast_opts = {'extract_flat': True, 'quiet': True}
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(fast_opts) as ydl:
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(search, download=False))

            if 'entries' in data:
                entries = list(data['entries'])
                if not entries: return await ctx.send("❌ No encontré resultados.")
                
                first_entry = entries[0]
                url = first_entry.get('url') or f"https://www.youtube.com/watch?v={first_entry.get('id')}"
                
                self.queues[ctx.guild.id].append({'titulo': first_entry.get('title'), 'url': url})
                if len(entries) > 1:
                    asyncio.create_task(self.background_load(ctx, entries[1:1500]))
                    await ctx.send(f"🚀 **Cargando lista...**")
                else:
                    await ctx.send(f"✅ Añadido: **{first_entry.get('title')}**")
            else:
                self.queues[ctx.guild.id].append({'titulo': data.get('title'), 'url': data.get('webpage_url') or search})
                await ctx.send(f"✅ Añadido: **{data.get('title')}**")

        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused() and not self.is_processing.get(ctx.guild.id, False):
            self.check_queue(ctx)

    @commands.command(aliases=['ap'])
    async def autoplay(self, ctx):
        self.autoplay_estado[ctx.guild.id] = not self.autoplay_estado.get(ctx.guild.id, False)
        estado = "ACTIVADO" if self.autoplay_estado[ctx.guild.id] else "DESACTIVADO"
        await ctx.send(f"📻 **Modo Radio:** {estado}")

    @commands.command()
    async def playnext(self, ctx, *, search: str):
        if not ctx.voice_client: await ctx.author.voice.channel.connect()
        if ctx.guild.id not in self.queues: self.queues[ctx.guild.id] = deque()
        if not search.startswith("http"): search = f"ytsearch:{search}"

        async with ctx.typing():
            fast_opts = {'extract_flat': True, 'quiet': True}
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(fast_opts) as ydl:
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(search, download=False))

            if 'entries' in data:
                entries = list(data['entries'])
                if not entries: return await ctx.send("❌ Sin resultados.")
                first_entry = entries[0]
                url = first_entry.get('url') or f"https://www.youtube.com/watch?v={first_entry.get('id')}"
                self.queues[ctx.guild.id].appendleft({'titulo': first_entry.get('title'), 'url': url})
                await ctx.send(f"⏭️ **A continuación:** {first_entry.get('title')}")
            else:
                self.queues[ctx.guild.id].appendleft({'titulo': data.get('title'), 'url': data.get('webpage_url') or search})
                await ctx.send(f"⏭️ **A continuación:** {data.get('title')}")

        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused() and not self.is_processing.get(ctx.guild.id, False):
            self.check_queue(ctx)

    @commands.command()
    async def q(self, ctx):
        if ctx.guild.id not in self.queues or not self.queues[ctx.guild.id]:
            return await ctx.send("La cola está vacía.")
        view = PaginationView(self.queues[ctx.guild.id])
        await ctx.send(embed=view.create_embed(), view=view)

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Pausado")

    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Reanudado")

    @commands.command()
    async def stop(self, ctx):
        if ctx.guild.id in self.queues: self.queues[ctx.guild.id].clear()
        if ctx.voice_client:
            ctx.voice_client.stop() 
            await ctx.voice_client.disconnect()
        self.now_playing_msgs.pop(ctx.guild.id, None)
        if platform.system() == "Windows":
            os.system("taskkill /f /im ffmpeg.exe >nul 2>&1")
        else:
            os.system("pkill -9 ffmpeg > /dev/null 2>&1")
        await ctx.send("🛑 Bot detenido.")

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("⏭️ **Saltada**")

    @commands.command()
    async def remove(self, ctx, index: int):
        if ctx.guild.id not in self.queues or not self.queues[ctx.guild.id]:
            return await ctx.send("Vacío.")
        try:
            removed = self.queues[ctx.guild.id][index-1]
            del self.queues[ctx.guild.id][index-1]
            await ctx.send(f"❌ Quitada: **{removed['titulo']}**")
        except:
            await ctx.send("⚠️ Índice inválido.")

    @commands.command()
    async def shuffle(self, ctx):
        if ctx.guild.id not in self.queues or len(self.queues[ctx.guild.id]) < 2:
            return await ctx.send("No hay suficiente para mezclar.")
        lista_cola = list(self.queues[ctx.guild.id])
        random.shuffle(lista_cola)
        self.queues[ctx.guild.id] = deque(lista_cola)
        await ctx.send("🔀 **Cola mezclada.**")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        voice_client = member.guild.voice_client
        if not voice_client: return
        if before.channel is not None and len(voice_client.channel.members) == 1:
            if member.guild.id in self.queues:
                self.queues[member.guild.id].clear()
            self.now_playing_msgs.pop(member.guild.id, None)
            if platform.system() == "Windows":
                os.system("taskkill /f /im ffmpeg.exe >nul 2>&1")
            else:
                os.system("pkill -9 ffmpeg > /dev/null 2>&1")
            await voice_client.disconnect()

async def setup(bot):
    await bot.add_cog(Music(bot))