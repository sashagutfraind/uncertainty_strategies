<img src="./walls_garden_titan2.png" width="300" height="300" alt='illustration'>

# Strategies for uncertainty
This repo holds the Risk-reducing Design and Operations Toolkit (RDOT), a catalogue of strategies for managing
risk and uncertainty, with materials accompanying the papers below.

## Papers
- Gutfraind, A. (2023, revised 2025). [On strategies for risk management and decision making under uncertainty shared across multiple fields](https://arxiv.org/pdf/2309.03133). arXiv:2309.03133.
  Introduces RDOT: more than 110 strategies, such as robust design and contingency planning, that recur across engineering, planning and other fields yet fit neither probabilistic models nor cognitive heuristics. It groups them into six categories, argues they help under radical uncertainty and unknown unknowns, and proposes ways to bring them into decision theory.
- Gutfraind, A. (2024). [Defining the analytical complexity of decision problems under uncertainty based on their pivotal properties](https://peerj.com/articles/cs-2195/). *PeerJ Computer Science* 10:e2195. doi:10.7717/peerj-cs.2195.
  Reviews over 90 strategies that expert decision-makers, such as engineers and military planners, use to cope with uncertainty, and finds that many decision problems have pivotal properties, such as a small action space or reversibility, that make them solvable despite uncertainty. It defines a quantitative analytical-complexity score for a decision problem based on which of these properties are available.
- Gutfraind, A. & Bier, V. (2025). [From nuclear safety to LLM security: Applying non-probabilistic risk management strategies to build safe and secure LLM-powered systems](https://arxiv.org/abs/2505.17084). arXiv:2505.17084.
  Argues that probabilistic risk analysis copes poorly with the novelty, complexity and adaptive adversaries of LLM-powered systems. It maps more than 100 RDOT strategies, drawn from fields such as nuclear and civil engineering, to LLM security and AI safety, and describes an LLM-powered workflow for applying them.
- Shi, L. & Gutfraind, A. (2025). [Sustainability-focused generative AI risk mitigation strategies](https://rpsonline.com.sg/proceedings/esrel-sra-e2025/html/ESREL-SRA-E2025-P6517.html). Proceedings of ESREL 2025 and SRA-E 2025, Stavanger, Norway.
  Applies RDOT to generative AI applications in the sustainability domain, drawing on an internal enterprise GenAI application to cover risk identification, testing, evaluation and mitigation. It finds 34 of the 111 strategies already in use in that application and 17 more unused but highly promising.

## Materials
- [Listing of RDOT strategies (csv file)](strategies_uncertainty_latest.csv)
- [Risk management for AI solutions (slides PDF)](AI%20risk%20management%20with%20RDOT-%20PSAM%20talk%202023.pdf)

## Tools
- [RDOT Advisor MCP server](tools/rdot-advisor-mcp/): lets AI coding agents (VS Code, Kiro and other MCP clients) look up RDOT strategies and cite them when reviewing an architecture, system design or code.

## License
[MIT](LICENSE)
