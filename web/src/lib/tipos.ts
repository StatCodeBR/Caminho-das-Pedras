/** O que a API entrega no evento final. Espelha o resumo de `api/app/principal.py`. */

export type Recurso = {
	titulo: string;
	link: string;
	formato: string;
	disponivel: boolean;
};

export type Conjunto = {
	nome: string;
	titulo: string;
	orgao: string;
	confianca: 'alta' | 'media' | 'baixa';
	url_portal: string;
	pontuacao: number;
	/**
	 * Quando os dados mudaram. Nulo é valor legítimo: falta em cerca de um
	 * quinto do catálogo, e nunca deve ser suprido pela data dos metadados.
	 */
	dados_atualizados_em: string | null;
	/** Quando o registro no portal foi editado. Não diz nada sobre o dado. */
	metadados_atualizados_em: string | null;
	recursos: Recurso[];
};

export type Origem =
	| 'correspondencia_direta'
	| 'redigida_pelo_modelo'
	| 'nao_encontrado'
	| 'modo_reduzido';

export type EventoFim = {
	origem: Origem;
	fichas: Conjunto[];
	latencia_ms: number;
};
