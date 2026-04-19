import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

MI_ID = 466025612092375051
bot_bloqueado = False

class CoreBot(commands.Bot):
    async def setup_hook(self):
        await self.load_extension('cogs.music')

intents = discord.Intents.default()
intents.message_content = True
bot = CoreBot(command_prefix='$', intents=intents, help_command=None, case_insensitive=True)

@bot.check
async def check_lockdown(ctx):
    if ctx.command and ctx.command.name in ["lock", "reload"]:
        return True
    if not bot_bloqueado:
        return True
    return ctx.author.id == MI_ID

@bot.command()
async def lock(ctx):
    global bot_bloqueado
    if ctx.author.id != MI_ID:
        return 
    bot_bloqueado = not bot_bloqueado
    estado = "ACTIVADO (Solo Admin)" if bot_bloqueado else "DESACTIVADO (Público)"
    await ctx.send(f"🔒 **Modo bloqueo:** {estado}")

@bot.command()
async def reload(ctx):
    if ctx.author.id != MI_ID:
        return
    try:
        await bot.reload_extension('cogs.music')
        await ctx.send("🔄 Módulo de música recargado.")
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="🤖 Panel de Comandos - MusicBot",
        description="Usa el prefijo `$` seguido del comando.",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="🎵 Reproducción",
        value="`$play o $p [busqueda/link]` - Suena una canción o lista." \
        "\n`$autoplay` - Activa el modo radio." \
        "\n`$playnext [busqueda]` - Pon una canción al principio de la cola." \
        "\n`$pause` - Pausa.\n`$resume` - Reanuda.\n`$skip` - Salta.",
        inline=False
    )
    embed.add_field(
        name="📋 Gestión de Cola",
        value="`$q` - Ver cola.\n`$shuffle` - Mezclar.\n`$remove [Nº]` - Quitar canción.",
        inline=False
    )
    embed.add_field(name="⚙️ Sistema", value="`$stop` - Detiene y limpia todo.", inline=False)
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("🔒 **Acceso denegado:** Bot bloqueado o ID incorrecto.")

bot.run(os.getenv('DISCORD_TOKEN'))