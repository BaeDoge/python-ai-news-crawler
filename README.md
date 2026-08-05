# 🚀 AI News Crawler (KB TechLab)

<!-- GitHub 배지 영역: 프로젝트의 빌드 상태, 버전, 라이선스, 사용 기술 등을 시각적으로 표현 -->

<p align="center">
  <strong>KB TechLab Project - AI News Crawler</strong>
</p>
<p align="center">
  <strong>- 배배배와 친구들 - </strong>
</p>

<p align="center">
  <a href="https://your-demo-link.com"><strong>🌐 데모 영상 (Live Demo) »</strong></a>
</p>

<br />

---

## 📑 목차 (Table of Contents)
- [🚀 AI News Crawler (KB TechLab)](#-ai-news-crawler-kb-techlab)
  - [📑 목차 (Table of Contents)](#-목차-table-of-contents)
  - [📖 개요 (Overview)](#-개요-overview)
  - [✨ 핵심 기능 (Key Features)](#-핵심-기능-key-features)
  - [🛠 기술 스택 (Tech Stack)](#-기술-스택-tech-stack)
    - [](#)
    - [Data Processing \& PDF](#data-processing--pdf)
    - [Automation](#automation)
  - [🏁 시작하기 (Getting Started)](#-시작하기-getting-started)
    - [📋 사전 요구사항 (Prerequisites)](#-사전-요구사항-prerequisites)
    - [⚙️ 설치 및 실행 (Installation \& Setup)](#️-설치-및-실행-installation--setup)
  - [💡 사용 방법 (Usage)](#-사용-방법-usage)
    - [수집 대상 설정 (`config.yaml`)](#수집-대상-설정-configyaml)
    - [출력 결과물](#출력-결과물)
  - [👥 팀원 소개 (Team)](#-팀원-소개-team)
  - [📜 라이선스 (License)](#-라이선스-license)

---

## 📖 개요 (Overview)

**2026 TechLab** 연구형 IT-CoP

급변하는 IT 패러다임 속에서 신기술 동향 파악은 필수적이지만, 대다수 금융기관은 보안을 위해 강력한 내부망/외부망 분리 정책을 시행하고 있습니다. 이로 인해 임직원들이 외부 IT 미디어나 기술 블로그에 실시간으로 접근하는 데 물리적 제약이 따릅니다.

본 프로젝트는 이러한 문제를 해결하기 위해 외부망에서 양질의 기술 콘텐츠를 자동 수집·가공한 뒤, 사내 보안 규정(파일 반입 가이드라인)을 준수하는 정형화된 PDF 포맷으로 변환하여 안전하게 내부망으로 이관하는 자동화 프로세스를 구축합니다.

> **💡 개발 목적 (Problem & Solution)**
> - **문제 제기**: 작성예정
> - **해결 방안**: 작성예정

---

## ✨ 핵심 기능 (Key Features)

* **자동화된 콘텐츠 수집 (Crawling)**: 주요 IT 언론사, 글로벌 기술 블로그, 트렌드 사이트 대상 맞춤형 스크래핑
* **데이터 전처리 및 정제**: 본문 외 광고, 스크립트, 불필요한 레이아웃 등 노이즈 제거 및 핵심 텍스트 추출
* **정형 리포트 생성 (PDF)**: 사내 가독성을 고려한 커스텀 레이아웃 기반의 데일리 기술동향 PDF 자동 발행
* **내부망 반입 가이드 준수**: 악성코드 및 스크립트 위협 요소를 원천 차단한 정적 문서 형태의 파일 포맷 최적화

---

## 🛠 기술 스택 (Tech Stack)

### 
* 
* Playwright / BeautifulSoup4

### Data Processing & PDF
* Pandas (데이터 정제)
* ReportLab (PDF 레이아웃 빌드)

### Automation
* GitHub Actions / Crontab (스케줄링 주기 관리)


| Category | Technology |
| :--- | :--- |
| **Crawling & Engine** | <img src="https://shields.io"/> <img src="https://shields.io"/> |
| **Backend** | <img src="https://shields.io"/> <img src="https://shields.io"/> |
| **Database** | <img src="https://shields.io"/> |
| **DevOps** | <img src="https://shields.io"/> |

```text
[외부망 서버]                      [망간복사 시스템]               [은행 내부망]
+------------------------+      +---------------------+      +------------------------+

| 1. IT 기술 뉴스 수집   | ---> | 3. 파일 무결성 검사  | ---> | 4. 사내 지식포털 연동  |
| 2. 텍스트 정제 및 PDF  |      |    (보안성 심사)    |      | 5. 임직원 데일리 구독  |
+------------------------+      +---------------------+      +------------------------+
```

---

## 🏁 시작하기 (Getting Started)

### 📋 사전 요구사항 (Prerequisites)
* Python 3.10 이상 환경
* 외부망 인터넷 아웃바운드 통신 권한 (크롤러 작동용)

### ⚙️ 설치 및 실행 (Installation & Setup)

1. 저장소 클론
```bash
git clone https://github.com/BaeDoge/python-ai-news-crawler.git
cd python-ai-news-crawler
```

2. 가상환경 설정 및 의존성 패키지 설치 (uv)
```bash
python -m pip install uv
uv sync  # Windows 환경: venv\Scripts\activate
```

3. 크롤러 브라우저 바이너리 설치
```bash
playwright install
```

4. 스크립트 실행
```bash
python main.py
```

---

## 💡 사용 방법 (Usage)

### 수집 대상 설정 (`config.yaml`)
수집하고자 하는 기술 블로그나 뉴스 채널의 RSS 피드 및 타겟 URL 목록을 관리합니다.
```yaml
sources:
  - site_name: "TechCrunch"
    target_url: "https://techcrunch.com"
  - site_name: "Toss_Tech"
    target_url: "https://toss.tech"
```

### 출력 결과물
배치가 정상 가동되면 `dist/daily_report_[YYYYMMDD].pdf` 경로로 파일이 생성되며, 해당 파일이 사내 망간복사 프로세스를 타게 됩니다.

1. **로그인**: 소셜 로그인 또는 이메일 인증을 통해 접속합니다.
2. **대시보드**: 상단 메뉴를 통해 원하는 분석 데이터를 실시간으로 조회합니다.

---

## 👥 팀원 소개 (Team)

인기 레포지토리에서 자주 사용하는 깔끔한 프로필 그리드 테이블 형태입니다.

<table>
  <tr>
    <td align="center">
      <a href="https://github.com">
        <img src="./src/imgs/members/mem1.png" width="100px;" alt="팀원1 이름"/><br />
        <sub><b>배성재 (Bae Sungjae)</b></sub>
      </a><br />
      <sub>역할 A</sub>
    </td>
    <td align="center">
      <a href="https://github.com">
        <img src="./src/imgs/members/mem1.png" width="100px;" alt="팀원1 이름"/><br />
        <sub><b>배용균 (Bae Yongyun)</b></sub>
      </a><br />
      <sub>역할 B</sub>
    </td>
    <td align="center">
      <a href="https://github.com">
        <img src="./src/imgs/members/mem1.png" width="100px;" alt="팀원1 이름"/><br />
        <sub><b>배승호 (Bae SeungHo)</b></sub>
      </a><br />
      <sub>역할 A</sub>
    </td>

  </tr>
  <tr>
    <td align="center">
      <a href="https://github.com">
        <img src="./src/imgs/members/mem1.png" width="100px;" alt="팀원1 이름"/><br />
        <sub><b>신종은 (Bae Sungjae)</b></sub>
      </a><br />
      <sub>역할 A</sub>
    </td>
    <td align="center">
      <a href="https://github.com">
        <img src="./src/imgs/members/mem1.png" width="100px;" alt="팀원1 이름"/><br />
        <sub><b>이은창 (Bae Yongyun)</b></sub>
      </a><br />
      <sub>역할 B</sub>
    </td>
  </tr>
</table>

---

## 📜 라이선스 (License)

이 프로젝트는 **MIT License**를 따릅니다. 자세한 내용은 [LICENSE](./LICENSE) 파일을 참고하세요.