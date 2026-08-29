import streamlit as st
import requests
from bs4 import BeautifulSoup
import scrapy
from scrapy.crawler import CrawlerProcess
import multiprocessing
import re
import time
import urllib.parse
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import nltk
from nltk.corpus import stopwords



nltk.download('stopwords', quiet=True)
STOPWORDS_PT = set(stopwords.words('portuguese'))

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Web Scraping & NLP Wiki App",
    page_icon="📊",
    layout="wide"
)




def formatar_urls_wiki(texto_termos: str) -> list[str]:
    """
    Recebe os termos separados por vírgula e transforma em URLs válidas da Wikipédia.
    """
    termos = [termo.strip() for termo in texto_termos.split(",") if termo.strip()]
    urls_formatadas = []
    
    for termo in termos:
        termo_ajustado = termo.replace(" ", "_")
        termo_codificado = urllib.parse.quote(termo_ajustado, safe=":/_")
        urls_formatadas.append(f"https://pt.wikipedia.org/wiki/{termo_codificado}")
        
    return urls_formatadas


def limpar_e_filtrar_stopwords(texto_bruto: str) -> list[str]:
    """
    Normaliza o texto, remove numerações de referências da Wiki ([1], [2]),
    remove pontuações e filtra as stopwords em português.
    """
    texto_sem_refs = re.sub(r'\[\d+\]', ' ', texto_bruto.lower())
    
    tokens = re.findall(r'[a-záàâãéèêíïóôõöúçñ]+', texto_sem_refs)
    
    tokens_limpos = [w for w in tokens if w not in STOPWORDS_PT and len(w) > 2]
    
    return tokens_limpos




def extrair_com_bs4(urls: list[str]) -> str:
    """
    Executa a raspagem sequencial/síncrona utilizando Requests e BeautifulSoup.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    textos_coletados = []
    
    for url in urls:
        try:
            resposta = requests.get(url, headers=headers, timeout=10)
            if resposta.status_code == 200:
                sopa = BeautifulSoup(resposta.text, 'html.parser')
                paragrafos = sopa.find_all('p')
                texto_pagina = " ".join([p.get_text() for p in paragrafos])
                textos_coletados.append(texto_pagina)
            else:
                st.warning(f"⚠️ URL indisponível ({resposta.status_code}): {url}")
        except Exception as erro:
            st.error(f"❌ Falha ao acessar {url}: {erro}")
            
    return " ".join(textos_coletados)




class WikiSpider(scrapy.Spider):
    """Spider do Scrapy para extração concorrente de tags <p>."""
    name = "wiki_spider"
    custom_settings = {
        'LOG_LEVEL': 'ERROR',
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    def __init__(self, urls=None, queue=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = urls or []
        self.queue = queue
        self.conteudos = []

    def parse(self, response):
        paragrafos = response.css('p::text').getall()
        self.conteudos.append(" ".join(paragrafos))

    def closed(self, reason):
        if self.queue is not None:
            self.queue.put(" ".join(self.conteudos))


def _processo_isolado_scrapy(urls: list[str], fila: multiprocessing.Queue):
    """Executa o CrawlerProcess em subprocesso isolado para não travar o loop."""
    processo = CrawlerProcess()
    processo.crawl(WikiSpider, urls=urls, queue=fila)
    processo.start()


def extrair_com_scrapy(urls: list[str]) -> str:
    """
    Invoca o subprocesso concorrente do Scrapy e aguarda os dados.
    """
    fila = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_processo_isolado_scrapy, args=(urls, fila))
    proc.start()
    proc.join(timeout=25)
    
    if not fila.empty():
        return fila.get()
    return ""




st.title("📊 Data App: Web Scraping, NLP & Nuvem de Palavras")
st.markdown("Aplicação analítica para extração de páginas da Wikipédia, limpeza de stopwords e estatística de termos.")

st.sidebar.header("⚙️ Parâmetros de Execução")

termos_padrao = (
    "Universidade Federal do Rio Grande do Norte, "
    "Ciência de Dados, "
    "Aprendizado de Máquina, "
    "Engenharia de Software, "
    "Armazém de Dados"
)

texto_termos = st.sidebar.text_area(
    "Digite 5 termos separados por vírgula:",
    value=termos_padrao,
    height=120
)

palavra_busca = st.sidebar.text_input(
    "Palavra-chave para contagem no texto final:",
    value="dados"
)

metodo_escolhido = st.sidebar.radio(
    "Escolha o método de extração:",
    ["Requests + BeautifulSoup (Síncrono)", "Scrapy (Assíncrono)"]
)

botao_executar = st.sidebar.button("🚀 Executar Extração", type="primary")

if botao_executar:
    urls_alvo = formatar_urls_wiki(texto_termos)
    palavra_chave_limpa = palavra_busca.strip().lower()
    
    if not urls_alvo:
        st.error("Por favor, informe termos válidos.")
    elif not palavra_chave_limpa:
        st.error("Por favor, informe uma palavra-chave para contagem.")
    else:
        st.subheader("🌐 URLs Alvo Geradas")
        st.write(urls_alvo)
        
        with st.spinner("Realizando coleta dos dados e processamento..."):
            inicio_tempo = time.perf_counter()
            
            if metodo_escolhido == "Requests + BeautifulSoup (Síncrono)":
                texto_bruto_acumulado = extrair_com_bs4(urls_alvo)
            else:
                texto_bruto_acumulado = extrair_com_scrapy(urls_alvo)
                
            fim_tempo = time.perf_counter()
            tempo_execucao = fim_tempo - inicio_tempo

        if not texto_bruto_acumulado.strip():
            st.error("Nenhum conteúdo pôde ser extraído das URLs. Verifique a grafia dos termos.")
        else:
            tokens_limpos = limpar_e_filtrar_stopwords(texto_bruto_acumulado)
            string_limpa_final = " ".join(tokens_limpos)
            
            total_palavra = tokens_limpos.count(palavra_chave_limpa)
            total_palavras_geral = len(tokens_limpos)
            
            st.divider()
            col1, col2, col3 = st.columns(3)
            col1.metric("⏱️ Tempo de Coleta", f"{tempo_execucao:.3f} s")
            col2.metric("📝 Total de Palavras (Limpas)", f"{total_palavras_geral:,}")
            col3.metric(f"🎯 Ocorrências de '{palavra_chave_limpa}'", f"{total_palavra} vezes")
            
            st.divider()
            st.subheader("☁️ Nuvem de Palavras (Frequência Geral)")
            
            if tokens_limpos:
                wordcloud = WordCloud(
                    width=1000,
                    height=450,
                    background_color="white",
                    colormap="viridis",
                    max_words=120
                ).generate(string_limpa_final)
                
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.imshow(wordcloud, interpolation="bilinear")
                ax.axis("off")
                st.pyplot(fig)
            else:
                st.warning("O texto extraído não contém palavras suficientes para gerar a nuvem.")