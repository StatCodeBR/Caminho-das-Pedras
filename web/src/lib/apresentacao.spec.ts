import { describe, expect, it } from 'vitest';
import {
	descreverAtualizacao,
	descreverOrigem,
	formatosDe,
	nomeDoOrgao,
	podeEnviar,
	recursosVisiveis
} from './apresentacao';
import type { Conjunto } from './tipos';

function conjunto(extra: Partial<Conjunto> = {}): Conjunto {
	return {
		nome: 'x',
		titulo: 'X',
		orgao: 'ministerio-da-saude',
		confianca: 'alta',
		url_portal: 'https://dados.gov.br/dados/conjuntos-dados/x',
		pontuacao: 1,
		dados_atualizados_em: null,
		metadados_atualizados_em: null,
		recursos: [],
		...extra
	};
}

describe('descreverAtualizacao', () => {
	it('usa a data dos dados quando ela existe', () => {
		const a = descreverAtualizacao(
			conjunto({
				dados_atualizados_em: '2023-05-01T00:00:00+00:00',
				metadados_atualizados_em: '2024-09-09T14:46:52+00:00'
			})
		);
		expect(a.rotulo).toBe('dados atualizados em');
		expect(a.incerta).toBe(false);
		expect(a.texto).toContain('2023');
	});

	it('não substitui a data dos dados pela dos metadados sem avisar', () => {
		// Registro editado em 2024, dados de nunca: dizer "2024" faria o leitor
		// supor um frescor que o dado não tem.
		const a = descreverAtualizacao(
			conjunto({ metadados_atualizados_em: '2024-09-09T14:46:52+00:00' })
		);
		expect(a.rotulo).toBe('registro editado em');
		expect(a.incerta).toBe(true);
		expect(a.texto).toContain('2024');
	});

	it('diz que a data não foi informada quando faltam as duas', () => {
		const a = descreverAtualizacao(conjunto());
		expect(a.texto).toBe('não informada');
		expect(a.incerta).toBe(true);
		// Nada de traço mudo, que o leitor interpretaria como quiser.
		expect(a.texto).not.toBe('-');
	});

	it('trata data ilegível como ausente em vez de exibir lixo', () => {
		const a = descreverAtualizacao(conjunto({ dados_atualizados_em: 'ontem' }));
		expect(a.texto).toBe('não informada');
	});
});

describe('descreverOrigem', () => {
	it('traduz a origem para linguagem de quem não conhece o sistema', () => {
		expect(descreverOrigem('correspondencia_direta')).toBe('encontrado direto no catálogo');
		expect(descreverOrigem('redigida_pelo_modelo')).not.toContain('modelo_');
	});

	it('devolve vazio quando não há origem', () => {
		expect(descreverOrigem(null)).toBe('');
	});
});

describe('formatosDe', () => {
	it('reúne formatos sem repetir, em maiúsculas', () => {
		const c = conjunto({
			recursos: [
				{ titulo: 'a', link: 'l', formato: 'csv', disponivel: true },
				{ titulo: 'b', link: 'l', formato: 'CSV', disponivel: true },
				{ titulo: 'c', link: 'l', formato: 'json', disponivel: false }
			]
		});
		expect(formatosDe(c)).toEqual(['CSV', 'JSON']);
	});

	it('devolve lista vazia quando não há formato declarado', () => {
		expect(formatosDe(conjunto())).toEqual([]);
	});
});

describe('nomeDoOrgao', () => {
	it('troca hifens por espaços', () => {
		expect(nomeDoOrgao('ministerio-da-saude')).toBe('ministerio da saude');
	});

	it('não deixa o campo vazio sem explicação', () => {
		expect(nomeDoOrgao('')).toBe('órgão não informado');
	});
});

describe('recursosVisiveis', () => {
	it('põe os disponíveis primeiro sem omitir os que estão fora do ar', () => {
		const c = conjunto({
			recursos: [
				{ titulo: 'morto', link: 'l', formato: 'csv', disponivel: false },
				{ titulo: 'vivo', link: 'l2', formato: 'csv', disponivel: true }
			]
		});
		const { visiveis, ocultos } = recursosVisiveis(c);
		expect(visiveis.map((r) => r.titulo)).toEqual(['vivo', 'morto']);
		// O indisponível continua na lista: foi catalogado, e quem procura tem
		// direito de saber que existe e não abre.
		expect(visiveis).toHaveLength(2);
		expect(ocultos).toBe(0);
	});

	it('limita a lista e informa quantos ficaram de fora', () => {
		const c = conjunto({
			recursos: Array.from({ length: 9 }, (_, i) => ({
				titulo: `r${i}`,
				link: 'l',
				formato: 'csv',
				disponivel: true
			}))
		});
		const { visiveis, ocultos } = recursosVisiveis(c);
		expect(visiveis).toHaveLength(6);
		expect(ocultos).toBe(3);
	});

	it('não altera a lista original', () => {
		const c = conjunto({
			recursos: [
				{ titulo: 'morto', link: 'l', formato: 'csv', disponivel: false },
				{ titulo: 'vivo', link: 'l2', formato: 'csv', disponivel: true }
			]
		});
		recursosVisiveis(c);
		expect(c.recursos[0].titulo).toBe('morto');
	});
});

describe('podeEnviar', () => {
	it('recusa pergunta vazia ou só de espaços', () => {
		expect(podeEnviar('', false)).toBe(false);
		expect(podeEnviar('   ', false)).toBe(false);
	});

	it('recusa envio enquanto a busca anterior não terminou', () => {
		expect(podeEnviar('dengue', true)).toBe(false);
	});

	it('aceita pergunta com texto e nenhuma busca em curso', () => {
		expect(podeEnviar('dengue', false)).toBe(true);
	});
});
