'''
MIT License
Copyright (c) 2017 Grok
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import discord
from discord.ext import commands
from discord.ext.commands import TextChannelConverter
from contextlib import redirect_stdout
from ext.utility import load_json
from urllib.parse import quote as uriquote
from mtranslate import translate
from lxml import etree
from ext import fuzzy
from ext import embedtobox
from PIL import Image
import unicodedata
import traceback
import textwrap
import aiohttp
import inspect
import asyncio
import time
import re
import io
import os
import random
import json
import base64
import requests

class Utility:
    '''Useful commands to make your life easier'''

    def __init__(self, bot):
        self.bot = bot
        self.lang_conv = load_json('data/langs.json')
        self._last_embed = None
        self._rtfm_cache = None
        self._last_google = None
        self._last_result = None


    @commands.command(name='help')
    async def new_help_command(self, linu, *commands: str):
        """Shows this message."""
        destination = linu.message.author if self.bot.pm_help else linu.message.channel

        def repl(obj):
            return self.bot._mentions_transforms.get(obj.group(0), '')

        # help by itself just lists our own commands.
        if len(commands) == 0:
            pages = await self.bot.formatter.format_help_for(linu, self.bot)
        elif len(commands) == 1:
            # try to see if it is a cog name
            name = self.bot._mention_pattern.sub(repl, commands[0])
            command = None
            if name in self.bot.cogs:
                command = self.bot.cogs[name]
            else:
                command = self.bot.all_commands.get(name)
                if command is None:
                    await destination.send(self.bot.command_not_found.format(name))
                    return

            pages = await self.bot.formatter.format_help_for(linu, command)
        else:
            name = self.bot._mention_pattern.sub(repl, commands[0])
            command = self.bot.all_commands.get(name)
            if command is None:
                await destination.send(self.bot.command_not_found.format(name))
                return

            for key in commands[1:]:
                try:
                    key = self.bot._mention_pattern.sub(repl, key)
                    command = command.all_commands.get(key)
                    if command is None:
                        await destination.send(self.bot.command_not_found.format(key))
                        return
                except AttributeError:
                    await destination.send(self.bot.command_has_no_subcommands.format(command, key))
                    return

            pages = await self.bot.formatter.format_help_for(linu, command)

        if self.bot.pm_help is None:
            characters = sum(map(lambda l: len(l), pages))
            # modify destination based on length of pages.
            if characters > 1000:
                destination = linu.message.author

        color = await linu.get_dominant_color(linu.author.avatar_url)

        for embed in pages:
            embed.color = color
            try:
                await linu.send(embed=embed)
            except discord.HTTPException:
                em_list = await embedtobox.etb(embed)
                for page in em_list:
                    await linu.send(page)


    @commands.command()
    async def source(self, linu, *, command):
        '''See the source code for any command.'''
        try:
            source = str(inspect.getsource(self.bot.get_command(command).callback))
            fmt = '```py\n' + source.replace('`', '\u200b`') + '\n```'
            await linu.send(fmt)
        except AttributeError:
            await linu.send("Thats not a command")

    @commands.group(aliases=['trans'])
    async def translate(self, ctx, lang, *, text):
        """Translate text!"""
        conv = self.lang_conv
        if lang in conv:
            return await ctx.send(f'*{translate(text, lang)}*')
        lang = dict(zip(conv.values(), conv.keys())).get(lang.lower().title())
        if lang:
            await ctx.send(f'*{translate(text, lang)}*')
        else:
            await ctx.send('`Language not available.`', delete_after=5)
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    @commands.command()
    async def langs(self, ctx):
        '''Lists all available languages'''
        codes = self.lang_conv
        em = discord.Embed(color=discord.Color.blue(),
                           title='Available Languages',
                           description=', '.join(codes.values()))
        await ctx.send(embed=em)


    @commands.command(pass_context=True)
    @commands.cooldown(rate=1, per=3.0, type=commands.BucketType.user)
    async def embed(self, linu, *, edescription: str):
        """makes you a embed"""
        embed = discord.Embed(description=edescription, color=0x36393e)
        embed.set_footer(text='Requested by:\n{0}'.format(linu.author))
        try:
            await linu.message.delete()
            await linu.send(
                embed=embed)

        except Exception:
            await linu.send(
                embed=embed)


    @commands.group(aliases=['rtfd'], invoke_without_command=True)
    async def rtfm(self, linu, *, obj: str = None):
        """
        Gives you a documentation link for a discord.py entity.
        Written by Rapptz
        """
        await self.do_rtfm(linu, 'rewrite', obj)


    async def to_embed(self, linu, params):
        '''Actually formats the parsed parameters into an Embed'''
        em = discord.Embed()

        if not params.count('{'):
            if not params.count('}'):
                em.description = params

        for field in self.get_parts(params):
            data = self.parse_field(field)

            color = data.get('color') or data.get('colour')
            if color == 'random':
                em.color = random.randint(0, 0xFFFFFF)
            elif color == 'chosen':
                maybe_col = os.environ.get('COLOR')
                if maybe_col:
                    raw = int(maybe_col.strip('#'), 16)
                    return discord.Color(value=raw)
                else:
                    return await linu.send('Chosen color is not defined.')

            elif color:
                color = int(color.strip('#'), 16)
                em.color = discord.Color(color)

            if data.get('description'):
                em.description = data['description']

            if data.get('desc'):
                em.description = data['desc']

            if data.get('title'):
                em.title = data['title']

            if data.get('url'):
                em.url = data['url']

            author = data.get('author')
            icon, url = data.get('icon'), data.get('url')

            if author:
                em._author = {'name': author}
                if icon:
                    em._author['icon_url'] = icon
                if url:
                    em._author['url'] = url

            field, value = data.get('field'), data.get('value')
            inline = False if str(data.get('inline')).lower() == 'false' else True
            if field and value:
                em.add_field(name=field, value=value, inline=inline)

            if data.get('thumbnail'):
                em._thumbnail = {'url': data['thumbnail']}

            if data.get('image'):
                em._image = {'url': data['image']}

            if data.get('footer'):
                em._footer = {'text': data.get('footer')}
                if data.get('icon'):
                    em._footer['icon_url'] = data.get('icon')

            if 'timestamp' in data.keys() and len(data.keys()) == 1:
                em.timestamp = linu.message.created_at

        return em

    def get_parts(self, string):
        '''
        Splits the sections of the embed command
        '''
        for i, char in enumerate(string):
            if char == "{":
                ret = ""
                while char != "}":
                    i += 1
                    char = string[i]
                    ret += char
                yield ret.rstrip('}')

    def parse_field(self, string):
        '''
        Recursive function to get all the key val
        pairs in each section of the parsed embed command
        '''
        ret = {}

        parts = string.split(':')
        key = parts[0].strip().lower()
        val = ':'.join(parts[1:]).strip()

        ret[key] = val

        if '|' in string:
            string = string.split('|')
            for part in string:
                ret.update(self.parse_field(part))
        return ret

    async def build_rtfm_lookup_table(self):
        cache = {}

        page_types = {
            'rewrite': (
                'http://discordpy.rtfd.io/en/rewrite/api.html',
                'http://discordpy.rtfd.io/en/rewrite/ext/commands/api.html'
            )
        }

        for key, pages in page_types.items():
            sub = cache[key] = {}
            for page in pages:
                async with self.bot.session.get(page) as resp:
                    if resp.status != 200:
                        raise RuntimeError('Cannot build rtfm lookup table, try again later.')

                    text = await resp.text(encoding='utf-8')
                    root = etree.fromstring(text, etree.HTMLParser())
                    if root is not None:
                        nodes = root.findall(".//dt/a[@class='headerlink']")
                        for node in nodes:
                            href = node.get('href', '')
                            as_key = href.replace('#discord.', '').replace('ext.commands.', '')
                            sub[as_key] = page + href

        self._rtfm_cache = cache

    async def do_rtfm(self, linu, key, obj):
        base_url = 'http://discordpy.rtfd.io/en/{}/'.format(key)

        if obj is None:
            await linu.send(base_url)
            return

        if not self._rtfm_cache:
            await linu.trigger_typing()
            await self.build_rtfm_lookup_table()

        # identifiers don't have spaces
        obj = obj.replace(' ', '_')

        if key == 'rewrite':
            pit_of_success_helpers = {
                'vc': 'VoiceClient',
                'msg': 'Message',
                'color': 'Colour',
                'perm': 'Permissions',
                'channel': 'TextChannel',
                'chan': 'TextChannel',
            }

            # point the abc.Messageable types properly:
            q = obj.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == '_':
                    continue
                if q == name:
                    obj = 'abc.Messageable.{}'.format(name)
                    break

            def replace(o):
                return pit_of_success_helpers.get(o.group(0), '')

            pattern = re.compile('|'.join(r'\b{}\b'.format(k)
                                          for k in pit_of_success_helpers.keys()))
            obj = pattern.sub(replace, obj)

        cache = self._rtfm_cache[key]
        matches = fuzzy.extract_or_exact(
            obj, cache, scorer=fuzzy.token_sort_ratio, limit=5, score_cutoff=50)

        e = discord.Embed(colour=discord.Colour.blurple())
        if len(matches) == 0:
            return await linu.send('Could not find anything. Sorry.')

        e.description = '\n'.join('[{}]({}) ({}%)'.format(key, url, p) for key, p, url in matches)
        await linu.send(embed=e)

    def parse_google_card(self, node):
        e = discord.Embed(colour=discord.Colour.blurple())

        # check if it's a calculator card:
        calculator = node.find(".//span[@class='cwclet']")
        if calculator is not None:
            e.title = 'Calculator'
            result = node.find(".//span[@class='cwcot']")
            if result is not None:
                result = ' '.join((calculator.text, result.text.strip()))
            else:
                result = calculator.text + ' ???'
            e.description = result
            return e

        # check for unit conversion card

        unit_conversions = node.xpath(".//input[contains(@class, '_eif') and @value]")
        if len(unit_conversions) == 2:
            e.title = 'Unit Conversion'

            # the <input> contains our values, first value = second value essentially.
            # these <input> also have siblings with <select> and <option selected=1>
            # that denote what units we're using

            # We will get 2 <option selected="1"> nodes by traversing the parent
            # The first unit being converted (e.g. Miles)
            # The second unit being converted (e.g. Feet)

            xpath = etree.XPath("parent::div/select/option[@selected='1']/text()")
            try:
                first_node = unit_conversions[0]
                first_unit = xpath(first_node)[0]
                first_value = float(first_node.get('value'))
                second_node = unit_conversions[1]
                second_unit = xpath(second_node)[0]
                second_value = float(second_node.get('value'))
                e.description = ' '.join(
                    (str(first_value), first_unit, '=', str(second_value), second_unit))
            except Exception:
                return None
            else:
                return e

        # check for currency conversion card
        if 'currency' in node.get('class', ''):
            currency_selectors = node.xpath(".//div[@class='ccw_unit_selector_cnt']")
            if len(currency_selectors) == 2:
                e.title = 'Currency Conversion'
                # Inside this <div> is a <select> with <option selected="1"> nodes
                # just like the unit conversion card.

                first_node = currency_selectors[0]
                first_currency = first_node.find("./select/option[@selected='1']")

                second_node = currency_selectors[1]
                second_currency = second_node.find("./select/option[@selected='1']")

                # The parent of the nodes have a <input class='vk_gy vk_sh ccw_data' value=...>
                xpath = etree.XPath("parent::td/parent::tr/td/input[@class='vk_gy vk_sh ccw_data']")
                try:
                    first_value = float(xpath(first_node)[0].get('value'))
                    second_value = float(xpath(second_node)[0].get('value'))

                    values = (
                        str(first_value),
                        first_currency.text,
                        f'({first_currency.get("value")})',
                        '=',
                        str(second_value),
                        second_currency.text,
                        f'({second_currency.get("value")})'
                    )
                    e.description = ' '.join(values)
                except Exception:
                    return None
                else:
                    return e

        # check for generic information card
        info = node.find(".//div[@class='_f2g']")
        if info is not None:
            try:
                e.title = ''.join(info.itertext()).strip()
                actual_information = info.xpath(
                    "parent::div/parent::div//div[@class='_XWk' or contains(@class, 'kpd-ans')]")[0]
                e.description = ''.join(actual_information.itertext()).strip()
            except Exception:
                return None
            else:
                return e

        # check for translation card
        translation = node.find(".//div[@id='tw-ob']")
        if translation is not None:
            src_text = translation.find(".//pre[@id='tw-source-text']/span")
            src_lang = translation.find(".//select[@id='tw-sl']/option[@selected='1']")

            dest_text = translation.find(".//pre[@id='tw-target-text']/span")
            dest_lang = translation.find(".//select[@id='tw-tl']/option[@selected='1']")

            # TODO: bilingual dictionary nonsense?

            e.title = 'Translation'
            try:
                e.add_field(name=src_lang.text, value=src_text.text, inline=True)
                e.add_field(name=dest_lang.text, value=dest_text.text, inline=True)
            except Exception:
                return None
            else:
                return e

        # check for "time in" card
        time = node.find("./div[@class='vk_bk vk_ans']")
        if time is not None:
            date = node.find("./div[@class='vk_gy vk_sh']")
            try:
                e.title = node.find('span').text
                e.description = f'{time.text}\n{"".join(date.itertext()).strip()}'
            except Exception:
                return None
            else:
                return e

        # time in has an alternative form without spans
        time = node.find("./div/div[@class='vk_bk vk_ans _nEd']")
        if time is not None:
            converted = "".join(time.itertext()).strip()
            try:
                # remove the in-between text
                parent = time.getparent()
                parent.remove(time)
                original = "".join(parent.itertext()).strip()
                e.title = 'Time Conversion'
                e.description = f'{original}...\n{converted}'
            except Exception:
                return None
            else:
                return e

        # check for definition card
        words = node.xpath(".//span[@data-dobid='hdw']")
        if words:
            lex = etree.XPath(".//div[@class='lr_dct_sf_h']/i/span")

            # this one is derived if we were based on the position from lex
            xpath = etree.XPath("../../../ol[@class='lr_dct_sf_sens']//"
                                "div[not(@class and @class='lr_dct_sf_subsen')]/"
                                "div[@class='_Jig']/div[@data-dobid='dfn']/span")
            for word in words:
                # we must go two parents up to get the root node
                root = word.getparent().getparent()

                pronunciation = root.find(".//span[@class='lr_dct_ph']/span")
                if pronunciation is None:
                    continue

                lexical_category = lex(root)
                definitions = xpath(root)

                for category in lexical_category:
                    definitions = xpath(category)
                    try:
                        descrip = [f'*{category.text}*']
                        for index, value in enumerate(definitions, 1):
                            descrip.append(f'{index}. {value.text}')

                        e.add_field(name=f'{word.text} /{pronunciation.text}/',
                                    value='\n'.join(descrip))
                    except:
                        continue

            return e

        # check for weather card
        location = node.find("./div[@id='wob_loc']")
        if location is None:
            return None

        # these units should be metric

        date = node.find("./div[@id='wob_dts']")

        # <img alt="category here" src="cool image">
        category = node.find(".//img[@id='wob_tci']")

        xpath = etree.XPath(
            ".//div[@id='wob_d']//div[contains(@class, 'vk_bk')]//span[@class='wob_t']")
        temperatures = xpath(node)

        misc_info_node = node.find(".//div[@class='vk_gy vk_sh wob-dtl']")

        if misc_info_node is None:
            return None

        precipitation = misc_info_node.find("./div/span[@id='wob_pp']")
        humidity = misc_info_node.find("./div/span[@id='wob_hm']")
        wind = misc_info_node.find("./div/span/span[@id='wob_tws']")

        try:
            e.title = 'Weather for ' + location.text.strip()
            e.description = f'*{category.get("alt")}*'
            e.set_thumbnail(url='https:' + category.get('src'))

            if len(temperatures) == 4:
                first_unit = temperatures[0].text + temperatures[2].text
                second_unit = temperatures[1].text + temperatures[3].text
                units = f'{first_unit} | {second_unit}'
            else:
                units = 'Unknown'

            e.add_field(name='Temperature', value=units, inline=False)

            if precipitation is not None:
                e.add_field(name='Precipitation', value=precipitation.text)

            if humidity is not None:
                e.add_field(name='Humidity', value=humidity.text)

            if wind is not None:
                e.add_field(name='Wind', value=wind.text)
        except:
            return None

        return e

    async def get_google_entries(self, query):
        url = f'https://www.google.com/search?q={uriquote(query)}'
        params = {
            'safe': 'on',
            'lr': 'lang_en',
            'hl': 'en'
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) Gecko/20100101 Firefox/53.0'
        }

        # list of URLs and title tuples
        entries = []

        # the result of a google card, an embed
        card = None

        async with self.bot.session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                #log.info('Google failed to respond with %s status code.', resp.status)
                raise RuntimeError('Google has failed to respond.')

            root = etree.fromstring(await resp.text(), etree.HTMLParser())

            # for bad in root.xpath('//style'):
            #     bad.getparent().remove(bad)

            # for bad in root.xpath('//script'):
            #     bad.getparent().remove(bad)

            # with open('google.html', 'w', encoding='utf-8') as f:
            #     f.write(etree.tostring(root, pretty_print=True).decode('utf-8'))

            """
            Tree looks like this.. sort of..
            <div class="rc">
                <h3 class="r">
                    <a href="url here">title here</a>
                </h3>
            </div>
            """

            card_node = root.xpath(".//div[@id='rso']/div[@class='_NId']//"
                                   "div[contains(@class, 'vk_c') or @class='g mnr-c g-blk' or @class='kp-blk']")

            if card_node is None or len(card_node) == 0:
                card = None
            else:
                card = self.parse_google_card(card_node[0])

            search_results = root.findall(".//div[@class='rc']")
            # print(len(search_results))
            for node in search_results:
                link = node.find("./h3[@class='r']/a")
                if link is not None:
                    # print(etree.tostring(link, pretty_print=True).decode())
                    entries.append((link.get('href'), link.text))

        return card, entries

    @commands.command(aliases=['g'])
    async def google(self, linu, *, query):
        """Searches google and gives you top result."""
        await linu.trigger_typing()
        try:
            card, entries = await self.get_google_entries(query)
        except RuntimeError as e:
            await linu.send(str(e))
        else:
            if card:
                value = '\n'.join(f'[{title}]({url.replace(")", "%29")})' for url,
                                  title in entries[:3])
                if value:
                    card.add_field(name='Search Results', value=value, inline=False)
                return await linu.send(embed=card)

            if len(entries) == 0:
                return await linu.send('No results found... sorry.')

            next_two = [x[0] for x in entries[1:3]]
            first_entry = entries[0][0]
            if first_entry[-1] == ')':
                first_entry = first_entry[:-1] + '%29'

            if next_two:
                formatted = '\n'.join(f'<{x}>' for x in next_two)
                msg = f'{first_entry}\n\n**See also:**\n{formatted}'
            else:
                msg = first_entry

            await linu.send(msg)

    async def edit_to_codeblock(self, linu, body, pycc='blank'):
        if pycc == 'blank':
            msg = f'{linu.prefix}eval\n```py\n{body}\n```'
        else:
            msg = f'{linu.prefix}cc make {pycc}\n```py\n{body}\n```'
        await linu.message.edit(content=msg)




    @commands.command()
    async def choose(self, linu, *, choices: commands.clean_content):
        '''Choose between multiple choices. Use `,` to seperate choices.'''
        choices = choices.split(',')
        if len(choices) < 2:
            return await linu.send('Not enough choices to pick from.')
        choices[0] = ' ' + choices[0]
        await linu.send(str(random.choice(choices))[1:])

#    @commands.command()
 #   async def update(self, linu):
  #      '''Auto Update command, checks if you have latest version
   #     Use tags github-token to find out how to set up this token'''
    #    git = self.bot.get_cog('Git')
     #   if not await git.starred('kyb3r/selfbot.py'): return await linu.send('**This command is disabled as the user have not starred <https://github.com/kyb3r/selfbot.py>**')
      #  # get username
       # username = await git.githubusername()
        #async with linu.session.get('https://api.github.com/repos/kyb3r/selfbot.py/git/refs/heads/rewrite', headers={"Authorization": f"Bearer {git.githubtoken}"}) as resp:
         #   if 300 > resp.status >= 200:
          #      async with linu.session.post(f'https://api.github.com/repos/{username}/selfbot.py/merges', json={"head": (await resp.json())['object']['sha'], "base": "rewrite", "commit_message": "Updating Bot"}, headers={"Authorization": f"Bearer {git.githubtoken}"}) as resp2:
           #         if 300 > resp2.status >= 200:
            #            if resp2.status == 204:
             #               return await linu.send('Already at latest version!')
              #          await linu.send('Bot updated! Restarting...')
               #     else:
                #        if resp2.status == 409:
                 #           return await linu.send('Merge conflict, you did some commits that made this fail!')
                  #      await linu.send('Well, I failed somehow, send the following to `4JR#2713` (180314310298304512) - resp2: ```py\n' + str(await resp2.json()) + '\n```')
            #else:
             #   await linu.send('Well, I failed somehow, send the following to `4JR#2713` (180314310298304512) - resp: ```py\n' + str(await resp.json()) + '\n```')

    @commands.command(pass_context=True)
    async def rpoll(self, linu, *, args):
        """Create a poll using reactions. {p}help rpoll for more information.
        {p}rpoll <question> | <answer> | <answer> - Create a poll. You may use as many answers as you want, placing a pipe | symbol in between them.
        Example:
        {p}rpoll What is your favorite anime? | Steins;Gate | Naruto | Attack on Titan | Shrek
        You can also use the "time" flag to set the amount of time in seconds the poll will last for.
        Example:
        {p}rpoll What time is it? | HAMMER TIME! | SHOWTIME! | time=10
        """
        await linu.message.delete()
        options = args.split(" | ")
        time = [x for x in options if x.startswith("time=")]
        if time:
            time = time[0]
        if time:
            options.remove(time)
        if len(options) <= 1:
            raise commands.errors.MissingRequiredArgument
        if len(options) >= 11:
            return await linu.send(self.bot.bot_prefix + "You must have 9 options or less.")
        if time:
            time = int(time.strip("time="))
        else:
            time = 30
        emoji = ['1⃣', '2⃣', '3⃣', '4⃣', '5⃣', '6⃣', '7⃣', '8⃣', '9⃣']
        to_react = []
        confirmation_msg = "**{}?**:\n\n".format(options[0].rstrip("?"))
        for idx, option in enumerate(options[1:]):
            confirmation_msg += "{} - {}\n".format(emoji[idx], option)
            to_react.append(emoji[idx])
        confirmation_msg += "\n\nYou have {} seconds to vote!".format(time)
        poll_msg = await linu.send(confirmation_msg)
        for emote in to_react:
            await poll_msg.add_reaction(emote)
        await asyncio.sleep(time)
        async for message in linu.message.channel.history():
            if message.id == poll_msg.id:
                poll_msg = message
        results = {}
        for reaction in poll_msg.reactions:
            if reaction.emoji in to_react:
                results[reaction.emoji] = reaction.count - 1
        end_msg = "The poll is over. The results:\n\n"
        for result in results:
            end_msg += "{} {} - {} votes\n".format(result, options[emoji.index(result)+1], results[result])
        top_result = max(results, key=lambda key: results[key])
        if len([x for x in results if results[x] == results[top_result]]) > 1:
            top_results = []
            for key, value in results.items():
                if value == results[top_result]:
                    top_results.append(options[emoji.index(key)+1])
            end_msg += "\nThe victory is tied between: {}".format(", ".join(top_results))
        else:
            top_result = options[emoji.index(top_result)+1]
            end_msg += "\n{} is the winner!".format(top_result)
        await linu.send(end_msg)

def setup(bot):
    bot.add_cog(Utility(bot))
