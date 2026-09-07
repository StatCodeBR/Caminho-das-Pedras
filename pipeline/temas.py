"""Lista fechada de temas das fichas.

Fechada de propósito: o modelo escolhe entre estes, e tema fora da lista é
descartado na validação. Sem isso, cada conjunto inventaria seu próprio
vocabulário e a busca por tema deixaria de funcionar.

Os rótulos são os que aparecem ao usuário final; as chaves são o que fica
gravado no banco e vai para o índice.
"""

TEMAS: dict[str, str] = {
    "saude": "Saúde",
    "educacao": "Educação",
    "seguranca": "Segurança pública",
    "justica": "Justiça e direitos",
    "assistencia-social": "Assistência social",
    "trabalho": "Trabalho e emprego",
    "economia": "Economia e finanças públicas",
    "agricultura": "Agricultura e pecuária",
    "meio-ambiente": "Meio ambiente e clima",
    "energia": "Energia",
    "transporte": "Transporte e mobilidade",
    "habitacao": "Habitação e saneamento",
    "cultura": "Cultura, esporte e lazer",
    "ciencia-tecnologia": "Ciência, tecnologia e inovação",
    "governo": "Governo e administração pública",
    "demografia": "População e território",
}


def valido(tema: str) -> bool:
    return tema in TEMAS


def filtrar(temas: list[str]) -> list[str]:
    """Descarta o que não está na lista, preservando o resto e a ordem."""
    vistos: set[str] = set()
    resultado: list[str] = []
    for tema in temas:
        chave = str(tema).strip().lower()
        if chave in TEMAS and chave not in vistos:
            vistos.add(chave)
            resultado.append(chave)
    return resultado


def para_prompt() -> str:
    """A lista como o prompt a apresenta ao modelo."""
    return "\n".join(f"- {chave}: {rotulo}" for chave, rotulo in TEMAS.items())
