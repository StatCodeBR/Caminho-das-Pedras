/**
 * Subconjunto mínimo de markdown para a área de resposta.
 *
 * Só negrito, itálico e parágrafo. O texto vem de um modelo de linguagem, e
 * tudo que não for explicitamente permitido aqui chega ao usuário como texto
 * literal.
 *
 * Duas recusas deliberadas:
 *
 * **Nada de HTML.** O escape acontece antes de qualquer conversão, então uma
 * marcação vinda do modelo — por acidente ou porque alguém a plantou numa
 * descrição do catálogo — aparece escrita, não executada. É o mesmo princípio
 * da guarda de saída da API: verificar em vez de confiar.
 *
 * **Nada de link clicável.** Endereço no texto continua sendo texto. Os links
 * ficam nos cartões, onde saem da ficha e passaram pela guarda de ancoragem.
 * Um link clicável montado a partir do que o modelo escreveu seria justamente
 * o caminho pelo qual uma URL inventada viraria clique.
 */

const ESCAPES: Record<string, string> = {
	'&': '&amp;',
	'<': '&lt;',
	'>': '&gt;',
	'"': '&quot;',
	"'": '&#39;'
};

function escapar(texto: string): string {
	return texto.replace(/[&<>"']/g, (ch) => ESCAPES[ch]);
}

/**
 * Converte o trecho de uma linha, já escapado, aplicando ênfase.
 *
 * O negrito vem antes do itálico para que `**` não seja consumido como dois
 * `*` soltos. O itálico aceita só asterisco, nunca sublinhado: os slugs do
 * portal são cheios de `_` — `equipe_saude_familia` viraria
 * `equipe<em>saude</em>familia`.
 */
function enfase(escapado: string): string {
	return escapado
		.replace(/\*\*(\S(?:[^*]*\S)?)\*\*/g, '<strong>$1</strong>')
		.replace(/\*(\S(?:[^*]*\S)?)\*/g, '<em>$1</em>');
}

/** O HTML da resposta: parágrafos, quebras, negrito e itálico. Nada mais. */
export function paraHtml(texto: string): string {
	if (!texto || !texto.trim()) return '';

	// Parágrafo é linha em branco. Quebra simples vira <br>, porque o template
	// da API monta listas de arquivos uma por linha.
	return (texto.trim().split(/\n\s*\n/) as string[])
		.map((bloco) =>
			bloco
				.split(/\n/)
				.map((linha) => enfase(escapar(linha)))
				.join('<br>')
		)
		.filter((bloco) => bloco.length > 0)
		.map((bloco) => `<p>${bloco}</p>`)
		.join('');
}
