import discord

ydl_opts = {
    'format': '251/bestaudio/best',
    'noplaylist': False,
    'quiet': True,
    'no_warnings': True,
    'extractor_args': {'youtube': {'player_client': ['android', 'ios']}}
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -loglevel quiet -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 -ac 2 -b:a 192k'
}

class PaginationView(discord.ui.View):
    def __init__(self, songs, per_page=15):
        super().__init__(timeout=60)
        self.songs = songs
        self.per_page = per_page
        self.current_page = 1
        self.total_pages = (len(songs) - 1) // per_page + 1

    def create_embed(self):
        start = (self.current_page - 1) * self.per_page
        end = start + self.per_page
        curr_songs = list(self.songs)[start:end]
        
        lista = "\n".join([f"{i+start+1}. [{s['titulo']}]({s['url']})" for i, s in enumerate(curr_songs)])
        embed = discord.Embed(title=f"📋 Cola ({len(self.songs)} canciones)", description=lista, color=discord.Color.orange())
        embed.set_footer(text=f"Página {self.current_page} de {self.total_pages}")
        return embed

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.gray)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Siguiente", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()