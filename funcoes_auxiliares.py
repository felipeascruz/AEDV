"""Funções auxiliares para a análise do desempenho olímpico e das características socioeconômicas.

O módulo reúne as etapas de coleta e preparação dos dados usadas no notebook:

1. coleta dos indicadores do World Bank (população, PIB e PIB per capita);
2. padronização dos códigos de país (ISO do World Bank -> NOC dos dados olímpicos);
3. construção da base país × edição, incluindo os países que não conquistaram medalhas;
4. junção da base olímpica com os indicadores socioeconômicos;
5. verificação dos países olímpicos sem correspondência no World Bank.
"""

from pathlib import Path

import pandas as pd


# =============================================================================
# Constantes
# =============================================================================

# Códigos oficiais dos indicadores do World Bank e nomes das colunas correspondentes:
# SP.POP.TOTL: população total
# NY.GDP.MKTP.CD: PIB (US$ correntes)
# NY.GDP.PCAP.CD: PIB per capita (US$ correntes)
INDICADORES_WB = {
    'SP.POP.TOTL': 'population',
    'NY.GDP.MKTP.CD': 'gdp',
    'NY.GDP.PCAP.CD': 'gdp_per_capita'
}

# Período solicitado à API do World Bank (anos inclusos)
ANO_INICIAL_WB = 1960
ANO_FINAL_WB = 2025

# Conversão dos códigos ISO do World Bank para os códigos NOC da base olímpica.
# Códigos que já são iguais nas duas bases (ex.: USA, BRA, FRA) não precisam constar aqui.
ISO_PARA_NOC = {
    'DZA': 'ALG', 'AGO': 'ANG', 'ATG': 'ANT', 'ABW': 'ARU',
    'ASM': 'ASA', 'BHS': 'BAH', 'BGD': 'BAN', 'BRB': 'BAR',
    'BMU': 'BER', 'BTN': 'BHU', 'BLZ': 'BIZ', 'BWA': 'BOT',
    'BHR': 'BRN', 'BRN': 'BRU', 'BGR': 'BUL', 'BFA': 'BUR',
    'KHM': 'CAM', 'CYM': 'CAY', 'COG': 'CGO', 'TCD': 'CHA',
    'CHL': 'CHI', 'CRI': 'CRC', 'HRV': 'CRO', 'DNK': 'DEN',
    'SLV': 'ESA', 'FJI': 'FIJ', 'GMB': 'GAM', 'GNB': 'GBS',
    'GNQ': 'GEQ', 'DEU': 'GER', 'GRC': 'GRE', 'GRD': 'GRN',
    'GTM': 'GUA', 'GIN': 'GUI', 'HTI': 'HAI', 'HND': 'HON',
    'IDN': 'INA', 'IRN': 'IRI', 'VIR': 'ISV', 'VGB': 'IVB',
    'XKX': 'KOS', 'SAU': 'KSA', 'KWT': 'KUW', 'LVA': 'LAT',
    'LBY': 'LBA', 'LSO': 'LES', 'MDG': 'MAD', 'MYS': 'MAS',
    'MWI': 'MAW', 'MNG': 'MGL', 'MCO': 'MON', 'MUS': 'MRI',
    'MRT': 'MTN', 'MMR': 'MYA', 'NIC': 'NCA', 'NLD': 'NED',
    'NPL': 'NEP', 'NGA': 'NGR', 'NER': 'NIG', 'OMN': 'OMA',
    'PRY': 'PAR', 'PHL': 'PHI', 'PSE': 'PLE', 'PRT': 'POR',
    'PRI': 'PUR', 'ZAF': 'RSA', 'WSM': 'SAM', 'SYC': 'SEY',
    'KNA': 'SKN', 'SVN': 'SLO', 'SLB': 'SOL', 'LKA': 'SRI',
    'SDN': 'SUD', 'CHE': 'SUI', 'TZA': 'TAN', 'TON': 'TGA',
    'TGO': 'TOG', 'ARE': 'UAE', 'URY': 'URU', 'VUT': 'VAN',
    'VNM': 'VIE', 'VCT': 'VIN', 'ZMB': 'ZAM', 'ZWE': 'ZIM',
}

# O código CHI do World Bank corresponde a Channel Islands e conflita com o NOC CHI do Chile.
# Channel Islands não compete como um NOC próprio, então esse código é removido do World Bank.
ISO_REMOVIDO_WB = 'CHI'

# O código olímpico do Líbano mudou na própria base: LIB até 2016 e LBN a partir de 2020.
# O World Bank usa LBN em todos os anos, então apenas os anos até 2016 precisam ser convertidos.
ULTIMO_ANO_LIB = 2016

COLUNAS_MEDALHAS = ['gold', 'silver', 'bronze', 'total']

CAMINHO_CSV_WB = 'world_bank.csv'


# =============================================================================
# World Bank: coleta e leitura
# =============================================================================

def reorganizar_world_bank(df: pd.DataFrame, indicadores = INDICADORES_WB) -> pd.DataFrame:
    """Converte o formato da API (um ano por coluna) em uma linha por país × ano.

    Args:
        df: Data Frame do World BAnk a ser reorganizado.
        indicadores: Dicionário contendo os nomes a serem modificados.
            Antigos são chave e novos são valor.
    Returns:
        Data Frame com colunas iso, country, year e uma coluna para cada indicador.
            Combinações de país e ano em que todos os indicadores estão ausentes não aparecem
            no resultado (comportamento do pivot_table).
    """
    # Transforma as colunas de anos em uma única coluna 'year'
    df = df.melt(
        id_vars=['economy', 'series', 'Country', 'Series'],
        var_name='year',
        value_name='valor'
    )

    # Pivota a tabela para que cada indicador ganhe a sua própria coluna
    df = df.pivot_table(
        index=['economy', 'Country', 'year'],
        columns='series',
        values='valor'
    ).reset_index()

    df['year'] = df['year'].astype(int)

    # Renomeia as colunas para facilitar a junção com os dados olímpicos
    return df.rename(columns={**indicadores, 'economy': 'iso', 'Country': 'country'})


def coletar_world_bank(
    caminho=CAMINHO_CSV_WB,
    indicadores=INDICADORES_WB,
    ano_inicial=ANO_INICIAL_WB,
    ano_final=ANO_FINAL_WB
):
    """Baixa os indicadores pela API do World Bank e salva em CSV, se o arquivo ainda não existir.

    O CSV é salvo já reorganizado, com uma linha por país × ano. Se o arquivo existir,
    ele é reutilizado e nenhuma consulta à API é feita.

    Args:
        caminho: Caminho para salvar o csv.
        indicadores: Dicionário com as chaves a serem buscadas no World Bank e os valores com os nomes
            a substituírem as chaves.
        ano_inicial: Ano inicial da busca na API.
        ano_final: Ano final da busca na API.
    """
    if Path(caminho).exists():
        return

    import wbgapi as wb

    df = wb.data.DataFrame(
        indicadores.keys(),
        time=range(ano_inicial, ano_final + 1),
        labels=True,
        numericTimeKeys=True
    ).reset_index()

    reorganizar_world_bank(df, indicadores).to_csv(caminho, index=False)


def carregar_world_bank(caminho=CAMINHO_CSV_WB, indicadores=INDICADORES_WB) -> pd.DataFrame:
    """Lê o CSV do World Bank, com uma linha por país × ano e uma coluna por indicador.

    Também aceita o formato antigo do arquivo (um ano por coluna), que é
    reorganizado durante a leitura.

    Args:
        caminho: Caminho onde encontrar o csv.
        indicadores: Dicionário com nomes de colunas antigas nas chaves a serem substituídas pelos valores.

    Returns:
        df: Data Frame encontrado.
    """

    df = reorganizar_world_bank(pd.read_csv(caminho), indicadores)

    return df


def adicionar_noc_world_bank(df: pd.DataFrame) -> pd.DataFrame:
    """Cria a coluna 'noc' a partir do código ISO, para permitir a junção com os dados olímpicos.

    Args:
        df: Data Frame do World Bank onde será criada a coluna.

    Returns:
        Data Frame atualizado com a coluna 'noc'.
    """
    df = df[df['iso'] != ISO_REMOVIDO_WB].copy()

    df['noc'] = df['iso'].replace(ISO_PARA_NOC)

    # Até 2016 o Líbano usa o código LIB; nos demais anos permanece LBN
    libano_ate_2016 = (df['iso'] == 'LBN') & (df['year'] <= ULTIMO_ANO_LIB)
    df.loc[libano_ate_2016, 'noc'] = 'LIB'

    return df


# =============================================================================
# Dados olímpicos
# =============================================================================

def filtrar_verao_e_padronizar_noc(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém apenas os Jogos de Verão e unifica os códigos NOC equivalentes.

    Args:
        df: Data Frame a ser modificado. Deve ter a coluna 'season' com valores 'Summer'.

    Returns:
        Data Frame apenas com os Jogos de Verão e com NOCs corrigidos.
    """
    df = df[df['season'] == 'Summer'].copy()

    correcoes_noc_olimpico = {
        'ROC': 'RUS',  # Comitê Olímpico Russo -> Rússia
        'OAR': 'RUS'  # Atletas Olímpicos da Rússia -> Rússia (relevante apenas em edições de Inverno)
    }
    df['noc'] = df['noc'].replace(correcoes_noc_olimpico)

    return df


def agregar_medalhas_por_pais_edicao(df_medalhas: pd.DataFrame) -> pd.DataFrame:
    """Soma as medalhas por ano e NOC, obtendo uma única observação por país × edição.

    Isso é necessário porque, em 1956, Melbourne e a subedição equestre de
    Estocolmo aparecem em linhas separadas.

    Args:
        df_medalhas: Data Frame das medalhas.

    Returns:
        Data Frame com as medalhas somadas.
    """
    return (
        df_medalhas
        .groupby(['year', 'noc'], as_index=False)
        .agg(
            country=('country', 'first'),
            gold=('gold', 'sum'),
            silver=('silver', 'sum'),
            bronze=('bronze', 'sum'),
            total=('total', 'sum')
        )
    )


def construir_base_olimpica(df_medalhas: pd.DataFrame, df_atletas: pd.DataFrame) -> pd.DataFrame:
    """Cria a base país × edição com todos os participantes, inclusive os sem medalhas.

    Os participantes vêm da base de atletas; as medalhas, do quadro de medalhas.

    Args:
        df_medalhas: Data Frame das medalhas.
        df_atletas: Data Frame dos atletas.

    Returns:
        Data Frame com os dados agregados.
    """
    df_medalhas_pais_edicao = agregar_medalhas_por_pais_edicao(df_medalhas)
    df_participantes = df_atletas[['year', 'noc']].drop_duplicates()

    df = df_participantes.merge(
        df_medalhas_pais_edicao,
        on=['year', 'noc'],
        how='left',
        validate='one_to_one'
    )

    # Ausência no quadro de medalhas significa participação com zero medalhas, não dado ausente
    df[COLUNAS_MEDALHAS] = df[COLUNAS_MEDALHAS].fillna(0).astype(int)

    return df


# =============================================================================
# Junção das bases e verificação
# =============================================================================

def combinar_com_world_bank(df_olimpico: pd.DataFrame, df_world_bank: pd.DataFrame) -> pd.DataFrame:
    """Une os dados olímpicos aos indicadores socioeconômicos por ano e NOC.

    Os países sem registro no World Bank são mantidos, com os indicadores ausentes (NaN).

    Args:
        df_olimpico: Data Frame com atletas e medalhas.
        df_world_bank: Data Frame com dados do World Bank.

    Returns:
        Data Frame com os dados agregados.
    """
    df = df_olimpico.merge(
        df_world_bank,
        on=['year', 'noc'],
        how='left',
        suffixes=('_olimpico', '_wb'),
        validate='one_to_one'
    )

    # Nome do país: usa o da base olímpica, depois o do World Bank e, por fim, o próprio código NOC
    df['country'] = (
        df['country_olimpico']
        .fillna(df['country_wb'])
        .fillna(df['noc'])
    )

    # Remove as colunas auxiliares que não são mais necessárias após a junção
    return df.drop(columns=['country_olimpico', 'country_wb', 'iso'])


def listar_noc_sem_world_bank(df_olimpico: pd.DataFrame, df_world_bank: pd.DataFrame, ano_inicial: int, ano_final: int)\
        -> pd.DataFrame:
    """Lista os NOCs participantes sem registro no World Bank no período informado.

    Args:
        df_olimpico: Data Frame com as medalhas e atletas.
        df_world_bank: Data Frame do World Bank.
        ano_inicial: Ano inicial da busca.
        ano_final: Ano final da busca.

    Returns:
        Retorna uma linha por NOC, com o nome do país, o número de edições sem registro,
        o primeiro e o último ano e o total de medalhas conquistadas nessas edições.
        Valores ausentes de países que possuem registro não entram nessa lista.
    """
    participantes = df_olimpico[df_olimpico['year'].between(ano_inicial, ano_final)]

    # Mesma chave usada na junção: ano + NOC
    chaves_world_bank = df_world_bank[['year', 'noc']].drop_duplicates()

    comparacao = participantes.merge(
        chaves_world_bank,
        on=['year', 'noc'],
        how='left',
        indicator=True
    )
    sem_registro = comparacao[comparacao['_merge'] == 'left_only']

    return (
        sem_registro
        .groupby('noc', as_index=False)
        .agg(
            pais=('country', 'first'),
            edicoes=('year', 'nunique'),
            primeiro_ano=('year', 'min'),
            ultimo_ano=('year', 'max'),
            medalhas=('total', 'sum')
        )
        .assign(pais=lambda d: d['pais'].fillna(d['noc']))
        .sort_values(['medalhas', 'edicoes'], ascending=False)
        .reset_index(drop=True)
    )
