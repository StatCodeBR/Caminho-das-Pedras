import { describe, expect, it } from 'vitest';
import { paraHtml } from './markdown';

describe('ênfase', () => {
	it('converte negrito', () => {
		expect(paraHtml('**Sinan/Dengue**')).toBe('<p><strong>Sinan/Dengue</strong></p>');
	});

	it('converte itálico', () => {
		expect(paraHtml('isto é *importante*')).toBe('<p>isto é <em>importante</em></p>');
	});

	it('não deixa o itálico comer os asteriscos do negrito', () => {
		expect(paraHtml('**a** e *b*')).toBe('<p><strong>a</strong> e <em>b</em></p>');
	});

	it('não trata sublinhado como itálico, para não quebrar slug do portal', () => {
		// `equipe_saude_familia` aparece nas respostas reais; virar
		// `equipe<em>saude</em>familia` estragaria o identificador.
		expect(paraHtml('use equipe_saude_familia')).toBe('<p>use equipe_saude_familia</p>');
	});

	it('deixa asterisco solto como texto', () => {
		expect(paraHtml('2 * 3 = 6')).toBe('<p>2 * 3 = 6</p>');
	});

	it('não cria ênfase vazia', () => {
		expect(paraHtml('a ** b')).toBe('<p>a ** b</p>');
	});
});

describe('parágrafos', () => {
	it('separa blocos por linha em branco', () => {
		expect(paraHtml('um\n\ndois')).toBe('<p>um</p><p>dois</p>');
	});

	it('quebra simples vira br, para as listas de arquivos do template', () => {
		expect(paraHtml('- a\n- b')).toBe('<p>- a<br>- b</p>');
	});

	it('devolve vazio para texto em branco', () => {
		expect(paraHtml('')).toBe('');
		expect(paraHtml('   \n  ')).toBe('');
	});
});

describe('recusa de HTML', () => {
	it('escapa marcação antes de qualquer conversão', () => {
		expect(paraHtml('<script>alert(1)</script>')).toBe(
			'<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>'
		);
	});

	it('escapa atributo com aspas', () => {
		expect(paraHtml('<img src=x onerror="alert(1)">')).toBe(
			'<p>&lt;img src=x onerror=&quot;alert(1)&quot;&gt;</p>'
		);
	});

	it('escapa ampersand sem duplicar a entidade', () => {
		expect(paraHtml('a & b')).toBe('<p>a &amp; b</p>');
		expect(paraHtml('&lt;')).toBe('<p>&amp;lt;</p>');
	});

	it('não deixa marcação escapar pela ênfase', () => {
		expect(paraHtml('**<b>x</b>**')).toBe('<p><strong>&lt;b&gt;x&lt;/b&gt;</strong></p>');
	});
});

describe('recusa de link clicável', () => {
	it('endereço no texto continua texto', () => {
		const html = paraHtml('veja https://dados.gov.br/dados/conjuntos-dados/x');
		expect(html).not.toContain('<a');
		expect(html).toContain('https://dados.gov.br/dados/conjuntos-dados/x');
	});

	it('sintaxe de link do markdown não vira âncora', () => {
		const html = paraHtml('[clique](https://exemplo.com)');
		expect(html).not.toContain('<a');
		expect(html).toContain('[clique](https://exemplo.com)');
	});

	it('javascript: não vira nada executável', () => {
		const html = paraHtml('[x](javascript:alert(1))');
		expect(html).not.toContain('<a');
		expect(html).not.toContain('href');
	});
});

describe('resposta real', () => {
	it('renderiza uma resposta do template sem produzir tag inesperada', () => {
		const texto =
			'**[Inativa] Gastos com Publicidade**\n\n' +
			'Registro dos gastos do Distrito Federal.\n\n' +
			'Quem publica: distrito federal.\n' +
			'Formatos disponíveis: CSV, PDF.\n\n' +
			'Página no portal: https://dados.gov.br/dados/conjuntos-dados/gastos-com-publicidade';
		const html = paraHtml(texto);
		const tags = [...html.matchAll(/<(\/?[a-z]+)/g)].map((m) => m[1]);
		expect(new Set(tags)).toEqual(new Set(['p', '/p', 'strong', '/strong', 'br']));
	});
});
