import { describe, expect, it } from 'vitest';
import { lerEventos, separar } from './sse';

function fluxo(...pedacos: string[]): ReadableStream<Uint8Array> {
	const cod = new TextEncoder();
	return new ReadableStream({
		start(controlador) {
			for (const p of pedacos) controlador.enqueue(cod.encode(p));
			controlador.close();
		}
	});
}

async function coletar(...pedacos: string[]) {
	const saida = [];
	for await (const ev of lerEventos(fluxo(...pedacos))) saida.push(ev);
	return saida;
}

describe('separar', () => {
	it('extrai um evento completo e devolve o resto', () => {
		const { eventos, resto } = separar('event: a\ndata: {"x":1}\n\nevent: b\ndata: {');
		expect(eventos).toEqual([{ nome: 'a', dados: { x: 1 } }]);
		expect(resto).toBe('event: b\ndata: {');
	});

	it('aceita fim de linha com retorno de carro, que proxies introduzem', () => {
		const { eventos } = separar('event: a\r\ndata: {"x":1}\r\n\r\n');
		expect(eventos).toEqual([{ nome: 'a', dados: { x: 1 } }]);
	});

	it('descarta evento com json malformado sem derrubar os demais', () => {
		const { eventos } = separar('event: a\ndata: {quebrado\n\nevent: b\ndata: 2\n\n');
		expect(eventos).toEqual([{ nome: 'b', dados: 2 }]);
	});

	it('ignora bloco sem linha de dados', () => {
		const { eventos } = separar(': comentário\n\n');
		expect(eventos).toEqual([]);
	});
});

describe('lerEventos', () => {
	it('remonta evento partido entre dois fragmentos', async () => {
		const evs = await coletar('event: fragmento\ndata: {"te', 'xto":"oi"}\n\n');
		expect(evs).toEqual([{ nome: 'fragmento', dados: { texto: 'oi' } }]);
	});

	it('emite dois eventos que chegaram no mesmo fragmento', async () => {
		const evs = await coletar('event: a\ndata: 1\n\nevent: b\ndata: 2\n\n');
		expect(evs.map((e) => e.nome)).toEqual(['a', 'b']);
	});

	it('emite o último evento mesmo sem linha em branco final', async () => {
		const evs = await coletar('event: fim\ndata: {"origem":"x"}');
		expect(evs).toEqual([{ nome: 'fim', dados: { origem: 'x' } }]);
	});

	it('preserva acento cortado entre dois fragmentos', async () => {
		// "ú" ocupa dois bytes: partir no meio produziria caractere inválido sem
		// a decodificação incremental. Em português isso acontece o tempo todo.
		const cod = new TextEncoder();
		const bytes = cod.encode('event: f\ndata: {"texto":"saúde"}\n\n');
		const corte = bytes.indexOf(0xc3) + 1;
		const stream = new ReadableStream<Uint8Array>({
			start(c) {
				c.enqueue(bytes.slice(0, corte));
				c.enqueue(bytes.slice(corte));
				c.close();
			}
		});
		const saida = [];
		for await (const ev of lerEventos(stream)) saida.push(ev);
		expect(saida).toEqual([{ nome: 'f', dados: { texto: 'saúde' } }]);
	});

	it('não emite nada para fluxo vazio', async () => {
		expect(await coletar()).toEqual([]);
	});
});

describe('ordem de entrega', () => {
	it('entrega o fragmento antes do evento final', async () => {
		const evs = await coletar(
			'event: fragmento\ndata: {"texto":"a"}\n\n',
			'event: fim\ndata: {"origem":"x"}\n\n'
		);
		expect(evs.map((e) => e.nome)).toEqual(['fragmento', 'fim']);
	});
});
