import { defineConfig } from 'vitest/config';
import tailwindcss from '@tailwindcss/vite';
import adapter from '@sveltejs/adapter-node';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) => filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: adapter(),
			// O SvelteKit assina os próprios scripts de hidratação com nonce, o
			// que permite proibir script inline sem quebrar a página — é a
			// diferença entre um CSP que protege e um com 'unsafe-inline', que
			// só decora.
			//
			// A aplicação não carrega nada de fora: sem fonte web, sem CDN, sem
			// analytics. Por isso `default-src 'self'` cabe sem exceção, e é o
			// que torna o CSP uma defesa de verdade para o `{@html}` da área de
			// resposta, onde entra texto escrito por um modelo.
			csp: {
				mode: 'auto',
				directives: {
					'default-src': ['self'],
					'script-src': ['self'],
					// `unsafe-inline` só em estilo, nunca em script. Atributo
					// `style=` não aceita nonce nem hash — a especificação do CSP
					// não os aplica a atributos —, e o próprio SvelteKit usa um
					// para manter oculto o `svelte-announcer`, a região que fala
					// com leitores de tela. Sem isto, ela aparece na página.
					//
					// A troca é assimétrica e por isso aceitável: injeção de
					// estilo desfigura, injeção de script executa. O que protege
					// contra XSS é o `script-src` acima, que continua estrito.
					'style-src': ['self', 'unsafe-inline'],
					'img-src': ['self', 'data:'],
					'font-src': ['self'],
					// A pergunta vai para a nossa própria rota de servidor, que
					// repassa à api. O navegador nunca fala com outro destino.
					'connect-src': ['self'],
					'object-src': ['none'],
					'base-uri': ['self'],
					'form-action': ['self'],
					// Clickjacking: ninguém embute esta página num iframe.
					'frame-ancestors': ['none'],
					'upgrade-insecure-requests': true
				}
			}
		})
	],
	test: {
		expect: { requireAssertions: true },
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'server',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
