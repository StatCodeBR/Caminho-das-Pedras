<script lang="ts">
	import { descreverAtualizacao, formatosDe, nomeDoOrgao, recursosVisiveis } from './apresentacao';
	import type { Conjunto } from './tipos';

	let { conjunto }: { conjunto: Conjunto } = $props();

	const atualizacao = $derived(descreverAtualizacao(conjunto));
	const formatos = $derived(formatosDe(conjunto));
	const lista = $derived(recursosVisiveis(conjunto));
	const indisponiveis = $derived(conjunto.recursos.filter((r) => !r.disponivel).length);
</script>

<article
	class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900"
>
	<h3 class="text-base font-semibold break-words text-slate-900 dark:text-slate-100">
		{conjunto.titulo || conjunto.nome}
	</h3>

	<p class="mt-1 text-sm break-words text-slate-600 dark:text-slate-400">
		{nomeDoOrgao(conjunto.orgao)}
	</p>

	<dl class="mt-3 space-y-1 text-sm">
		<div class="flex flex-wrap gap-x-2">
			<dt class="text-slate-500 dark:text-slate-400">{atualizacao.rotulo}:</dt>
			<dd
				class={atualizacao.incerta
					? 'text-slate-500 italic dark:text-slate-400'
					: 'text-slate-800 dark:text-slate-200'}
			>
				{atualizacao.texto}
			</dd>
		</div>
		{#if formatos.length}
			<div class="flex flex-wrap gap-x-2">
				<dt class="text-slate-500 dark:text-slate-400">formatos:</dt>
				<dd class="text-slate-800 dark:text-slate-200">{formatos.join(', ')}</dd>
			</div>
		{/if}
	</dl>

	{#if conjunto.recursos.length}
		<ul class="mt-3 space-y-1 text-sm">
			{#each lista.visiveis as recurso (recurso.titulo + recurso.link)}
				<li class="break-words">
					{#if recurso.disponivel && recurso.link}
						<a
							class="text-sky-700 underline underline-offset-2 hover:text-sky-900 dark:text-sky-400 dark:hover:text-sky-300"
							href={recurso.link}
							rel="noopener noreferrer"
							target="_blank">{recurso.titulo || 'arquivo sem nome'}</a
						>
					{:else}
						<span class="text-slate-500 line-through dark:text-slate-500">
							{recurso.titulo || 'arquivo sem nome'}
						</span>
						<!-- O recurso não some: ele foi catalogado, e quem procura tem
						     direito de saber que existe e não está acessível. -->
						<span class="text-xs text-amber-700 dark:text-amber-500">
							— link fora do ar quando verificamos
						</span>
					{/if}
				</li>
			{/each}
			{#if lista.ocultos}
				<li class="text-slate-500 dark:text-slate-400">
					e mais {lista.ocultos} na página do conjunto
				</li>
			{/if}
		</ul>
	{/if}

	{#if conjunto.confianca === 'baixa'}
		<p class="mt-3 text-xs text-slate-500 dark:text-slate-400">
			O órgão publicou pouca descrição sobre este conjunto. Confira os arquivos antes de
			usar.
		</p>
	{/if}

	<a
		class="mt-3 inline-block text-sm font-medium text-sky-700 underline underline-offset-2 hover:text-sky-900 dark:text-sky-400 dark:hover:text-sky-300"
		href={conjunto.url_portal}
		rel="noopener noreferrer"
		target="_blank"
	>
		Ver no portal de dados abertos
	</a>

	{#if indisponiveis}
		<p class="sr-only">{indisponiveis} arquivo(s) com link fora do ar.</p>
	{/if}
</article>
