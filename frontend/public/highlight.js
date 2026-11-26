const python = new Set('and as assert async await break case class continue def del elif else except False finally for from global if import in is lambda match None nonlocal not or pass raise return True try while with yield'.split(' '));
const common = new Set('abstract async await break case catch char class const continue default delete do double else enum export extends final finally float for if implements import int interface long new null private protected public return short static struct super switch this throw throws true try typedef typeof unsigned using void volatile while'.split(' '));
const extra = {
  javascript: 'as false from function in instanceof let of undefined var with yield',
  typescript: 'as boolean declare false from function in infer keyof let namespace never number of readonly satisfies string type undefined unknown var yield',
  java: 'assert boolean false instanceof native package record synchronized var',
  c: 'auto bool extern goto inline register restrict signed sizeof union',
  cpp: 'auto bool constexpr extern false goto inline namespace noexcept nullptr operator signed sizeof template typename union virtual',
};
const tokens = {
  python: /("""[\s\S]*?(?:"""|$)|'''[\s\S]*?(?:'''|$)|"(?:\\.|[^"\\\n])*"?|'(?:\\.|[^'\\\n])*'?|#[^\n]*)|\b(?:0[xob][\da-f]+|\d+(?:\.\d+)?)\b|\b[A-Za-z_]\w*\b/gi,
  generic: /(\/\*[\s\S]*?(?:\*\/|$)|\/\/[^\n]*|"(?:\\.|[^"\\\n])*"?|'(?:\\.|[^'\\\n])*'?|\x60(?:\\.|[^\x60\\])*\x60?)|\b(?:0[xob][\da-f]+|\d+(?:\.\d+)?)\b|\b[A-Za-z_$][\w$]*\b/gi,
};

export function highlight(element, text, language) {
  if (text.length > 60000) {
    element.textContent = text + '\n';
    return;
  }
  const pattern = language === 'python' ? tokens.python : tokens.generic;
  const keywords = language === 'python' ? python : new Set([...common, ...(extra[language] || '').split(' ')]);
  const fragment = document.createDocumentFragment();
  let offset = 0;
  for (const match of text.matchAll(pattern)) {
    const [lexeme, literal] = match;
    fragment.append(text.slice(offset, match.index));
    const comment = literal?.startsWith('#') || literal?.startsWith('//') || literal?.startsWith('/*');
    const type = literal ? (comment ? 'comment' : 'string')
      : keywords.has(lexeme) ? 'keyword' : /^\d/.test(lexeme) ? 'number' : null;
    if (type) {
      const token = document.createElement('span');
      token.className = 'token-' + type;
      token.textContent = lexeme;
      fragment.append(token);
    } else fragment.append(lexeme);
    offset = match.index + lexeme.length;
  }
  fragment.append(text.slice(offset), '\n');
  element.replaceChildren(fragment);
}
