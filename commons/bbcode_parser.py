import html as html_lib
import re

# Schémas d'URL autorisés dans les liens et images (le reste est neutralisé).
SAFE_URL = re.compile(r'^(https?:|mailto:|/|#|\?|[^:]*$)', re.IGNORECASE)
URL_ATTR = re.compile(r'(href|src)="([^"]*)"')
# [objet]42[/objet] : 42 = ligne d'inventaire (shop) du membre qui expose l'objet.
COLLECTIBLE_TAG = re.compile(r'\[objet\]\s*(\d{1,10})\s*\[/objet\]', re.IGNORECASE)
MAX_COLLECTIBLES_PER_TEXT = 6

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
            # [*] isolé hors d'une liste (les listes sont traitées avant, dans parse()).
            r'\[\*\]([^\n]*)': r'<li class="bbcode-list">\1</li>',
            r'\[t1\](.*?)\[/t1\]': r'<h2 style="font-size:2rem;font-weight:800;">\1</h2>',
            r'\[t2\](.*?)\[/t2\]': r'<h3 style="font-size:1.6rem;font-weight:600;">\1</h3>',
            r'\[t3\](.*?)\[/t3\]': r'<h4 style="font-size:1.4rem;font-weight:400;">\1</h4>',
            r'\[citation\](.*?)\[/citation\]': r'<fieldset class="quote-bbcode">\1</fieldset>',
            r'\[citation=(.*?)\](.*?)\[/citation\]': r'<fieldset class="quote-bbcode"><legend>\1</legend>\2</fieldset>',
            r'\[quote\](.*?)\[/quote\]': r'<fieldset class="quote-bbcode">\1</fieldset>',
            r'\[quote=(.*?)\](.*?)\[/quote\]': r'<fieldset class="quote-bbcode"><legend>\1</legend>\2</fieldset>',
            r'\[color=([#\w]+)\](.*?)\[/color\]': r'<span style="color: \1;">\2</span>',
            r'\[size=(\d{1,3})\](.*?)\[/size\]': r'<span style="font-size: \1px;">\2</span>',
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
    
    # Liste la plus interne d'abord, pour gérer les listes imbriquées.
    _innermost_list = re.compile(r'\[list\]((?:(?!\[list\]).)*?)\[/list\]\n?', re.DOTALL)

    def _handle_list(self, match):
        """[list][*]a[*]b[/list] -> <ul><li>a</li><li>b</li></ul>.

        Chaque [*] englobe le texte jusqu'au [*] suivant. Le HTML est produit
        sans retour à la ligne entre les éléments, pour que le filtre
        linebreaksbr n'insère pas de <br> parasites dans la liste.
        """
        inner = match.group(1)
        parts = re.split(r'\[\*\]', inner)
        if len(parts) > 1 and not parts[0].strip():
            parts = parts[1:]
        items = [part.strip() for part in parts if part.strip()]
        lis = ''.join(f'<li class="bbcode-list">{item}</li>' for item in items)
        return f'<ul class="bbcode-list">{lis}</ul>'

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

    def _extract_collectibles(self, text, cards):
        ids = []
        for match in COLLECTIBLE_TAG.finditer(text):
            pk = int(match.group(1))
            if pk not in ids:
                ids.append(pk)
        if not ids:
            return text
        entries = _collectible_entries(ids[:MAX_COLLECTIBLES_PER_TEXT])

        def replace(match):
            entry = entries.get(int(match.group(1)))
            cards.append(_collectible_card(entry))
            return f'@@OBJET_{len(cards) - 1}@@'

        return COLLECTIBLE_TAG.sub(replace, text)

    @staticmethod
    def _safe_url(match):
        value = html_lib.unescape(match.group(2))
        # Les navigateurs ignorent espaces et caractères de contrôle dans le schéma.
        compact = re.sub(r'[\x00-\x20]', '', value)
        if not SAFE_URL.match(compact):
            return f'{match.group(1)}="#"'
        return match.group(0)

    def parse(self, text, allow_html=True):
        """Convertit le BBCode en HTML.

        allow_html=False échappe tout HTML saisi : à utiliser pour le contenu
        écrit par les membres et les visiteurs. Le HTML brut n'est conservé que
        pour le contenu rédigé par l'équipe.
        """
        text = str(text or '')
        # Protège temporairement le contenu des balises [code]
        code_blocks = []
        def save_code(match):
            code_blocks.append(match.group(0))
            return f'@@CODE_BLOCK_{len(code_blocks)-1}@@'
            
        text = re.sub(r'\[code(?:=.*?)?\].*?\[/code\]', save_code, text, flags=re.DOTALL)

        if not allow_html:
            text = html_lib.escape(text, quote=True)

        # Objets de collection : remplacés par un repère, restaurés à la fin.
        collectibles = []
        text = self._extract_collectibles(text, collectibles)
        
        # Les listes d'abord : chaque [*] doit englober son texte.
        previous = None
        while previous != text:
            previous = text
            text = self._innermost_list.sub(self._handle_list, text)

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
            
            if not allow_html:
                lang = re.sub(r'[^\w+-]', '', lang) or 'none'
            text = text.replace(f'@@CODE_BLOCK_{i}@@', self._handle_code(content, lang))

        text = URL_ATTR.sub(self._safe_url, text)
        for i, card in enumerate(collectibles):
            text = text.replace(f'@@OBJET_{i}@@', card)
        return text


def _collectible_entries(ids):
    """{id de ligne d'inventaire: ligne} pour les objets de collection encore possédés."""
    try:
        from shop.models import Item
        from users.models import UserInventory
    except ImportError:  # pragma: no cover - apps absentes
        return {}
    entries = (UserInventory.objects.select_related('item', 'user')
               .filter(pk__in=ids, quantity__gt=0, item__kind=Item.KIND_COLLECTIBLE))
    return {entry.pk: entry for entry in entries}


def _collectible_card(entry):
    esc = html_lib.escape
    if entry is None:
        return ('<span class="collectible-card collectible-card--inline collectible-card--missing">'
                'Objet de collection indisponible</span>')
    item = entry.item
    url = item.visual_url
    visual = f'<img src="{esc(url)}" alt="">' if url else '<span aria-hidden="true">💎</span>'
    limited = ' · Série limitée' if item.is_limited else ''
    return (
        f'<span class="collectible-card collectible-card--inline collectible-card--{esc(item.rarity)}">'
        f'<span class="collectible-card__visual">{visual}</span>'
        f'<span class="collectible-card__text">'
        f'<strong class="collectible-card__name">{esc(item.name)}</strong><br>'
        f'<span class="collectible-card__rarity">{esc(item.get_rarity_display())}{limited}</span><br>'
        f'<span class="collectible-card__owner">Collection de {esc(entry.user.username)}</span>'
        f'</span></span>'
    )
