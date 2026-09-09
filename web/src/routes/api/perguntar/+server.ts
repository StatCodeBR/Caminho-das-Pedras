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

export const POST: RequestHandler = async ({ request, fetch, getClientAddress }) => {
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

	// A api nunca vê o navegador: ela é chamada daqui, então o socket dela é
	// sempre este container. Sem repassar o endereço, o limite por origem
	// contaria todos os visitantes como um só e o serviço se autolimitaria.
	//
	// `getClientAddress()` lê o cabeçalho configurado em ADDRESS_HEADER, e no
	// caso do X-Forwarded-For conta da direita conforme XFF_DEPTH — a direção
	// que o cliente não controla. Ler da esquerda seria confiar em quem envia.
	let origem = '';
	try {
		origem = getClientAddress();
	} catch {
		// adapter-node ergue quando ADDRESS_HEADER está configurado e ausente.
		// Sem endereço, a api cai no socket e todos compartilham o balde: pior
		// que o ideal, melhor que derrubar a requisição.
		origem = '';
	}

	let resposta: Response;
	try {
		resposta = await fetch(`${base}/perguntar`, {
			method: 'POST',
			headers: {
				'content-type': 'application/json',
				...(origem ? { 'x-origem-real': origem } : {})
			},
			body: JSON.stringify({ pergunta })
		});
	} catch {
		return respostaDeErro('O serviço de busca não está respondendo agora.');
	}

	if (resposta.status === 429) {
		// Recusa por excesso de perguntas da mesma origem. Vai pelo canal SSE,
		// em português, para a interface ter um caminho só de renderização.
		const espera = Number(resposta.headers.get('retry-after') ?? 60);
		const minutos = Math.max(1, Math.ceil(espera / 60));
		return respostaDeErro(
			`Você fez muitas perguntas em pouco tempo. Tente de novo em cerca de ${minutos} ` +
				`${minutos === 1 ? 'minuto' : 'minutos'}.`
		);
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
