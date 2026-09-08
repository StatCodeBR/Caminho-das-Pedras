/**
 * Repasse da pergunta à API de resposta.
 *
 * O navegador nunca fala direto com a API: assim ela não precisa de CORS aberto,
 * o endereço interno dela não vai ao cliente, e em produção só este container
 * fica exposto pelo Traefik.
 *
 * O corpo é devolvido sem acumular. Bufferizar aqui desfaria o streaming que a
 * API já entrega e transformaria a resposta numa entrega única — defeito que só
 * apareceria em produção, com proxy no caminho.
 */

import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

const API_PADRAO = 'http://localhost:8000';

export const POST: RequestHandler = async ({ request, fetch }) => {
	let pergunta = '';
	try {
		const corpo = await request.json();
		pergunta = typeof corpo?.pergunta === 'string' ? corpo.pergunta.trim() : '';
	} catch {
		pergunta = '';
	}

	if (!pergunta) {
		// Pergunta vazia não é erro do servidor: é ausência de pergunta.
		return new Response(null, { status: 204 });
	}

	const base = env.API_URL || API_PADRAO;

	let resposta: Response;
	try {
		resposta = await fetch(`${base}/perguntar`, {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: JSON.stringify({ pergunta })
		});
	} catch {
		return respostaDeErro('O serviço de busca não está respondendo agora.');
	}

	if (!resposta.ok || !resposta.body) {
		// O detalhe técnico fica no log do servidor, não na tela de quem perguntou.
		console.error('api respondeu', resposta.status);
		return respostaDeErro('O serviço de busca não está respondendo agora.');
	}

	return new Response(resposta.body, {
		headers: {
			'content-type': 'text/event-stream',
			'cache-control': 'no-cache',
			'x-accel-buffering': 'no'
		}
	});
};

/** Devolve o erro pelo mesmo canal SSE, para o cliente ter um caminho só. */
function respostaDeErro(mensagem: string): Response {
	const corpo = `event: erro\ndata: ${JSON.stringify({ mensagem })}\n\n`;
	return new Response(corpo, {
		headers: {
			'content-type': 'text/event-stream',
			'cache-control': 'no-cache',
			'x-accel-buffering': 'no'
		}
	});
}
