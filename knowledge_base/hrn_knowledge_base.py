# import asyncio
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.chunking.semantic import SemanticChunking
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder
from agno.vectordb.pgvector import PgVector, SearchType
from db.session import db_url
from knowledge_base.hrn_members import HrnMembers

# 0. TODO: add DOI-style citations referencing to every file in the knowledge base
# 1. TODO: replace Veronika's book chapter with a research article
# 2. TODO: impl async loading of knowledge base if startup time is too long: https://docs-v1.agno.com/vectordb/pgvector


def get_hrn_knowledge_base() -> Knowledge:
    knowledge_base = Knowledge(
        urls=__get_knoweldge_base_data(),
        vector_db=PgVector(
            db_url=db_url,
            table_name="research_papers",
            search_type=SearchType.hybrid,
            embedder=SentenceTransformerEmbedder(),
        ),
    )

    knowledge_base.add_content(
        __get_knoweldge_base_data(),
        reader=PDFReader(
            chunking_strategy=SemanticChunking(),
            read_images=True,
        ),
    )

    return knowledge_base


def __get_knoweldge_base_data() -> list:

    kb_data = [
        # 1. ROBERT BÖHM'S PAPERS
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/robert/Robert_Covid19HistoricalNarratives_2023.pdf",
            "metadata": HrnMembers.ROBERT.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/robert/Robert_CrowdsourcingInterventionsToBoostCovid19VaccineUptake_2022.pdf",
            "metadata": HrnMembers.ROBERT.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/robert/Robert_PandemicFatigueScale_2023.pdf",
            "metadata": HrnMembers.ROBERT.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/robert/Robert_PowerOfDefaultsIntergroupConflict_2022.pdf",
            "metadata": HrnMembers.ROBERT.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/robert/Robert_VaccineStatusIdentificationAndSocietalPoliarization_2022.pdf",
            "metadata": HrnMembers.ROBERT.to_metadata(),
        },
        # 2. JANINA'S PAPERS
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/janina/Janina_HealthForAllUniversalHealhtcare_2023.pdf",
            "metadata": HrnMembers.JANINA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/janina/Janina_MoralEconomyOfUniversalPublicHealthcare_2023.pdf",
            "metadata": HrnMembers.JANINA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/janina/Janina_MoreThanHumanPublicHealth_2020.pdf",
            "metadata": HrnMembers.JANINA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/janina/Janina_SpectacularInfrastructureMadridsPandemicHospital_2021.pdf",
            "metadata": HrnMembers.JANINA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/janina/Janina_The Hospital Multiple_2021.pdf",
            "metadata": HrnMembers.JANINA.to_metadata(),
        },
        # 3. JULIA'S PAPERS
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/julia/Julia_BasicPsychNeedsAgencyCommunionCovid19_2023.pdf",
            "metadata": HrnMembers.JULIA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/julia/Julia_BigTwoCovid19AgencyCommunionAdolescence_2022.pdf",
            "metadata": HrnMembers.JULIA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/julia/Julia_DepressionAnxietyHealthcareProfessionalsCovid19_2021.pdf",
            "metadata": HrnMembers.JULIA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/julia/Julia_MentalHealthOfHealthCareProfessionalsCovid19Pandemic_2023.pdf",
            "metadata": HrnMembers.JULIA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/julia/Julia_RoleOfMinorityDiscriminationAndPoliticalParticipationWrtDiscrimination_2022.pdf",
            "metadata": HrnMembers.JULIA.to_metadata(),
        },
        # 4. VERONIKA'S PAPERS
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/veronika/Veronika_Aligning-the-Affective-Body-Commercial-Surrogacy-2018.pdf",
            "metadata": HrnMembers.VERONIKA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/veronika/Veronika_BeginningsEndingsLifeEthonographicResearch_2022.pdf",
            "metadata": HrnMembers.VERONIKA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/veronika/Veronika_Intimate-Strangers-Commercial-Surrogacy-In-Russia-And-Ukraine_2023.pdf",
            "metadata": HrnMembers.VERONIKA.to_metadata(),
        },
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/veronika/Veronika_Not-Quite-Dead Ontological Careographies and the Ambiguous Fetal Body in the Context of Disability-PregnancyTerminationAustria_2024.pdf",
            "metadata": HrnMembers.VERONIKA.to_metadata(),
        },
    ]

    return kb_data
