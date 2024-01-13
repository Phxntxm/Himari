import io
import textwrap
import traceback
from contextlib import redirect_stdout
from typing import Literal, Optional

import discord
import sqlalchemy as sa  # noqa: F401
from discord.ext import commands


class Owner(commands.Cog):
    _last_result = None

    @staticmethod
    def cleanup_code(content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith("```") and content.endswith("```"):
            return "\n".join(content.split("\n")[1:-1])

        # remove `foo`
        return content.strip("` \n")

    @staticmethod
    def get_syntax_error(e):
        if e.text is None:
            return "```py\n{0.__class__.__name__}: {0}\n```".format(e)
        return "```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```".format(
            e, "^", type(e).__name__
        )

    @commands.is_owner()
    @commands.command()
    async def eval(self, ctx, *, body: str):
        env = {
            "bot": ctx.bot,
            "ctx": ctx,
            "channel": ctx.message.channel,
            "author": ctx.message.author,
            "server": ctx.message.guild,
            "guild": ctx.message.guild,
            "message": ctx.message,
            "self": self,
            "_": self._last_result,
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = "async def func():\n%s" % textwrap.indent(body, "  ")

        try:
            exec(to_compile, env)
        except SyntaxError as e:
            return await ctx.send(self.get_syntax_error(e))

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await ctx.send(f"```py\n{value}{traceback.format_exc()}\n```"[:2000])
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction("\u2705")
            except Exception:
                pass

            if ret is None:
                if value:
                    await ctx.send(f"```py\n{value}\n```"[:2000])
            else:
                self._last_result = ret
                await ctx.send(f"```py\n{value}{ret}\n```"[:2000])

    @commands.guild_only()
    @commands.is_owner()
    @commands.command()
    async def sync(
        self,
        ctx: commands.Context[commands.Bot],
        guilds: commands.Greedy[discord.Object],
        spec: Optional[Literal["~", "*", "^"]] = None,
    ) -> None:
        assert ctx.guild is not None

        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands (and all subcommands) "
                f"{'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
