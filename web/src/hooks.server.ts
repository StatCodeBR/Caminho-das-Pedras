/**
 * Cabeçalhos de segurança que o SvelteKit não emite sozinho.
 *
 * O `Content-Security-Policy` sai da configuração do Kit, em `vite.config.ts`,
 * porque só ele sabe assinar os próprios scripts de hidratação com nonce. O que
 * está aqui é o resto.
 */

import type { Handle } from '@sveltejs/kit';

const UM_ANO = 60 * 60 * 24 * 365;

export const handle: Handle = async ({ event, resolve }) => {
	const resposta = await resolve(event);

	// Impede o navegador de adivinhar o tipo do conteúdo. Sem isto, um arquivo
	// servido como texto pode ser interpretado como script.
	resposta.headers.set('x-content-type-options', 'nosniff');

	// Clickjacking. O CSP já traz `frame-ancestors`, mas navegadores antigos só
	// entendem este cabeçalho, e os dois juntos não conflitam.
	resposta.headers.set('x-frame-options', 'DENY');

	// Não vaza o caminho completo da página para sites de terceiros — o que a
	// pessoa perguntou não precisa viajar junto com o clique em um link.
	resposta.headers.set('referrer-policy', 'strict-origin-when-cross-origin');

	// Isolamento de origem: nenhuma janela aberta por aqui mantém referência
	// para este contexto.
	resposta.headers.set('cross-origin-opener-policy', 'same-origin');
	resposta.headers.set('cross-origin-resource-policy', 'same-origin');

	// Nada disso é usado pela aplicação; declarar explicitamente evita que um
	// script injetado peça acesso em nome do site.
	resposta.headers.set(
		'permissions-policy',
		'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
	);

	// HSTS só sobre HTTPS: em conexão simples o navegador ignora, e emiti-lo em
	// desenvolvimento local prenderia `localhost` a https no navegador do
	// desenvolvedor — erro difícil de diagnosticar depois.
	//
	// Sem `preload` de propósito: entrar na lista embutida dos navegadores é
	// praticamente irreversível e a decisão pertence a quem opera o domínio,
	// não a este arquivo.
	if (event.url.protocol === 'https:') {
		resposta.headers.set(
			'strict-transport-security',
			`max-age=${UM_ANO}; includeSubDomains`
		);
	}

	return resposta;
};
