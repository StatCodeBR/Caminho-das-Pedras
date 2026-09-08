/**
 * Analisador de Server-Sent Events sobre um fluxo de bytes.
 *
 * Usamos `fetch` com POST em vez de `EventSource` porque o nativo só faz GET e
 * não envia corpo — a pergunta iria na query string, visível no histórico do
 * navegador e nos logs de qualquer proxy no caminho.
 *
 * O preço é este analisador. O corte do fluxo não respeita a fronteira das
 * mensagens: um evento pode chegar partido ao meio, e dois eventos podem vir no
 * mesmo pedaço. Por isso o resto fica guardado entre as chamadas e só se emite
 * o que estiver completo.
 */

export type Evento = { nome: string; dados: unknown };

/** Separa os eventos completos de um texto, devolvendo o resto incompleto. */
export function separar(acumulado: string): { eventos: Evento[]; resto: string } {
	// Dois fins de linha encerram um evento. `\r\n` aparece quando há proxy no
	// caminho reescrevendo o fluxo, então os dois formatos são aceitos.
	const blocos = acumulado.split(/\r?\n\r?\n/);
	const resto = blocos.pop() ?? '';
	const eventos: Evento[] = [];

	for (const bloco of blocos) {
		let nome = 'message';
		const linhasDeDados: string[] = [];
		for (const linha of bloco.split(/\r?\n/)) {
			if (linha.startsWith('event:')) nome = linha.slice(6).trim();
			else if (linha.startsWith('data:')) linhasDeDados.push(linha.slice(5).trim());
		}
		if (!linhasDeDados.length) continue;
		const bruto = linhasDeDados.join('\n');
		try {
			eventos.push({ nome, dados: JSON.parse(bruto) });
		} catch {
			// Evento malformado é descartado em silêncio: derrubar a resposta
			// inteira por causa de um quadro corrompido seria pior para quem lê.
			continue;
		}
	}
	return { eventos, resto };
}

/** Lê o corpo da resposta e devolve os eventos conforme eles se completam. */
export async function* lerEventos(corpo: ReadableStream<Uint8Array>): AsyncGenerator<Evento> {
	const leitor = corpo.getReader();
	const decodificador = new TextDecoder();
	let acumulado = '';

	try {
		while (true) {
			const { done, value } = await leitor.read();
			if (done) break;
			// `stream: true` impede que um caractere multibyte cortado entre dois
			// pedaços vire caractere inválido — em português isso acontece o tempo
			// todo, porque acentos ocupam dois bytes.
			acumulado += decodificador.decode(value, { stream: true });
			const { eventos, resto } = separar(acumulado);
			acumulado = resto;
			for (const evento of eventos) yield evento;
		}
		acumulado += decodificador.decode();
		const { eventos } = separar(acumulado + '\n\n');
		for (const evento of eventos) yield evento;
	} finally {
		leitor.releaseLock();
	}
}
