/** Traduções da linguagem da API para a de quem vai ler a tela. */

import type { Conjunto, Origem } from './tipos';

const ORIGENS: Record<Origem, string> = {
	// A API declara nomes que servem à telemetria. Exibir a origem só é
	// honestidade se for compreensível para quem não sabe o que é um modelo.
	correspondencia_direta: 'encontrado direto no catálogo',
	redigida_pelo_modelo: 'resposta escrita a partir das fichas encontradas',
	nao_encontrado: 'nada encontrado no catálogo',
	modo_reduzido: 'não consegui redigir; veja os conjuntos encontrados'
};

export function descreverOrigem(origem: Origem | null): string {
	return origem ? (ORIGENS[origem] ?? '') : '';
}

export function nomeDoOrgao(bruto: string): string {
	return bruto ? bruto.replaceAll('-', ' ') : 'órgão não informado';
}

export function formatosDe(conjunto: Conjunto): string[] {
	const vistos = new Set<string>();
	for (const recurso of conjunto.recursos) {
		if (recurso.formato) vistos.add(recurso.formato.toUpperCase());
	}
	return [...vistos];
}

export const MAX_RECURSOS = 6;

/**
 * Os recursos a exibir, disponíveis primeiro, e quantos ficaram de fora.
 *
 * Recurso com link morto entra na lista marcado, nunca omitido: ele foi
 * catalogado, e quem procura tem direito de saber que existe e está fora do ar.
 */
export function recursosVisiveis(conjunto: Conjunto): {
	visiveis: Conjunto['recursos'];
	ocultos: number;
} {
	const ordenados = [...conjunto.recursos].sort(
		(a, b) => Number(b.disponivel) - Number(a.disponivel)
	);
	return {
		visiveis: ordenados.slice(0, MAX_RECURSOS),
		ocultos: Math.max(0, ordenados.length - MAX_RECURSOS)
	};
}

/** Pergunta vazia não vira requisição, e a anterior bloqueia a próxima. */
export function podeEnviar(pergunta: string, buscando: boolean): boolean {
	return pergunta.trim().length > 0 && !buscando;
}

export type Atualizacao = { texto: string; rotulo: string; incerta: boolean };

function formatarData(iso: string): string | null {
	const data = new Date(iso);
	if (Number.isNaN(data.getTime())) return null;
	return data.toLocaleDateString('pt-BR', {
		day: '2-digit',
		month: 'long',
		year: 'numeric'
	});
}

/**
 * A data exibida, dizendo de que data se trata.
 *
 * Um conjunto cujo registro foi editado ontem e cujos dados são de 2019 não é um
 * conjunto atualizado ontem. Cair silenciosamente para a data dos metadados
 * anunciaria um frescor que o dado não tem — mentira construída com informação
 * verdadeira. Quando falta tudo, dizemos que falta, em vez de um traço mudo que
 * o leitor interpretaria da forma mais otimista.
 */
export function descreverAtualizacao(conjunto: Conjunto): Atualizacao {
	const dados = conjunto.dados_atualizados_em && formatarData(conjunto.dados_atualizados_em);
	if (dados) {
		return { texto: dados, rotulo: 'dados atualizados em', incerta: false };
	}
	const meta =
		conjunto.metadados_atualizados_em && formatarData(conjunto.metadados_atualizados_em);
	if (meta) {
		return { texto: meta, rotulo: 'registro editado em', incerta: true };
	}
	return { texto: 'não informada', rotulo: 'data de atualização', incerta: true };
}
