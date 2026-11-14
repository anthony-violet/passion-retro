import re

class BBCodeParser:
    def __init__(self):
        # On défini ici les balises BBcode et leur équivalent en html
        self.bbcode_patterns = {
            r'\[b\](.*?)\[/b\]': r'<strong>\1</strong>',
            r'\[i\](.*?)\[/i\]': r'<i>\1</i>',
            r'\[u\](.*?)\[/u\]': r'<u>\1</u>',
            r'\[s\](.*?)\[/s\]': r'<strike>\1</strike>',
            r'\[url=(.*?)\](.*?)\[/url\]': r'<a href="\1">\2</a>',
            r'\[url\](.*?)\[/url\]': r'<a href="\1">\1</a>',
            r'\[url=(.*?)(?:\s+class=(.*?))?\](.*?)\[/url\]': lambda m: f'<a href="{m.group(1)}"{f" class={m.group(2)}" if m.group(2) else ""}>{{m.group(3)}}</a>',
            r'\[url\](?:\s+class=(.*?))?\](.*?)\[/url\]': lambda m: f'<a href="{m.group(2)}"{f" class={m.group(1)}" if m.group(1) else ""}>{{m.group(2)}}</a>',
            r'\[img alt=(.*?)\](.*?)\[/img\]': r'<img src="\2" alt="\1">',
            r'\[img\](.*?)\[/img\]': r'<img src="\1" alt="Image insérer par un utilisateur">',
            r'\[list\](.*?)\[/list\]': r'<ul class="bbcode-list">\1</ul>',
            r'\[\*\](.*?)': r'<li class="bbcode-list">\1</li>',
            r'\[t1\](.*?)\[/t1\]': r'<h2 style="font-size:2rem;font-weight:800;">\1</h2>',
            r'\[t2\](.*?)\[/t2\]': r'<h3 style="font-size:1.6rem;font-weight:600;">\1</h3>',
            r'\[t3\](.*?)\[/t3\]': r'<h4 style="font-size:1.4rem;font-weight:400;">\1</h4>',
            r'\[citation\](.*?)\[/citation\]': r'<fieldset class="quote-bbcode">\1</fieldset>',
            r'\[citation=(.*?)\](.*?)\[/citation\]': r'<fieldset class="quote-bbcode"><legend>\1</legend>\2</fieldset>',
            r'\[quote\](.*?)\[/quote\]': r'<fieldset class="quote-bbcode">\1</fieldset>',
            r'\[quote=(.*?)\](.*?)\[/quote\]': r'<fieldset class="quote-bbcode"><legend>\1</legend>\2</fieldset>',
            r'\[color=(.*?)\](.*?)\[/color\]': r'<span style="color: \1;">\2</span>',
            r'\[size=(.*?)\](.*?)\[/size\]': r'<span style="font-size: \1px;">\2</span>',
            r'\[p](.*?)\[/p\]': r'<p>\1</p>',
            r'\[center\](.*?)\[/center\]': r'<div style="text-align:center;">\1</div>',
            r'\[right\](.*?)\[/right\]': r'<div style="text-align:right;">\1</div>',
            r'\[hr\]': r'<hr />',
            r'---': r'<hr />',
            r'\[block\](.*?)\[/block\]': r'<div>\1</div>',
            r'\[block style=(.*?)\](.*?)\[/block\]': r'<div style="\1">\2</div>',
            r'\[block class=(.*?)\](.*?)\[/block\]': r'<div class="\1">\2</div>',
            r'\[block style=(.*?) class=(.*?)\](.*?)\[/block\]': r'<div style="\1" class="\2">\3</div>',
            r'\[code\](.*?)\[/code\]': lambda m: self._handle_code(m.group(1)),
            r'\[code=(.*?)\](.*?)\[/code\]': lambda m: self._handle_code(m.group(2), m.group(1)),
        }
    
    def _handle_code(self, content, language='none'):
        # Convertit les retours à la ligne en \n littéraux
        escaped_content = (
            content
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;')
            .replace('\r\n', '\n')  # Normalise les retours à la ligne Windows
            .replace('\r', '\n')    # Normalise les retours à la ligne Mac
        )
        # Enveloppe dans pre/code sans modifier les \n
        return f'''<pre class="language-{language}"><code class="language-{language}">{escaped_content}</code></pre>'''

    def parse(self, text):
        # Protège temporairement le contenu des balises [code]
        code_blocks = []
        def save_code(match):
            code_blocks.append(match.group(0))
            return f'@@CODE_BLOCK_{len(code_blocks)-1}@@'
            
        text = re.sub(r'\[code(?:=.*?)?\].*?\[/code\]', save_code, text, flags=re.DOTALL)
        
        # Parse les autres BBCodes
        for bbcode, html in self.bbcode_patterns.items():
            if callable(html):
                text = re.sub(bbcode, html, text, flags=re.DOTALL)
            else:
                text = re.sub(bbcode, html, text, flags=re.DOTALL)

        # Restaure les blocs de code
        for i, code_block in enumerate(code_blocks):
            if '=' in code_block:  # code avec langage spécifié
                lang = re.match(r'\[code=(.*?)\]', code_block).group(1)
                content = re.search(r'\[code=.*?\](.*?)\[/code\]', code_block, re.DOTALL).group(1)
            else:  # code sans langage
                lang = 'none'
                content = re.search(r'\[code\](.*?)\[/code\]', code_block, re.DOTALL).group(1)
            
            text = text.replace(f'@@CODE_BLOCK_{i}@@', self._handle_code(content, lang))
            
        return text