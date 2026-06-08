
export interface Job {
  id: string;
  name: string;
  category: string;
  heat: number;
  duties: string;
  requiredSkills: string[];
  bonusSkills: string[];
  scenarios: string;
  status: 'pending' | 'active' | 'archived';
  source: string;
  date: string;
}

export interface Skill {
  id: string;
  name: string;
  level: 'beginner' | 'intermediate' | 'advanced';
  category: string;
  desc?: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'job' | 'skill';
  category?: string;
}

export interface GraphLink {
  source: string;
  target: string;
}

export const mockJobs: Job[] = [
  {
    id: 'j1',
    name: 'AI 提示词工程师',
    category: 'AI',
    heat: 95,
    duties: '负责设计、优化和测试 AI 提示词，提升模型输出质量。',
    requiredSkills: ['NLP', '提示词工程', 'Python'],
    bonusSkills: ['LLM 微调', '数据分析'],
    scenarios: '互联网、内容创作、自动化办公',
    status: 'active',
    source: '智联招聘',
    date: '2025-05-20'
  },
  {
    id: 'j2',
    name: '大数据架构师',
    category: '大数据',
    heat: 88,
    duties: '设计高可用的大数据处理架构，处理海量数据流。',
    requiredSkills: ['Hadoop', 'Spark', 'Flink'],
    bonusSkills: ['云原生', '数据安全'],
    scenarios: '金融、电商、政务',
    status: 'active',
    source: '猎聘',
    date: '2025-05-18'
  },
  {
    id: 'j3',
    name: '物联网系统专家',
    category: '物联网',
    heat: 82,
    duties: '负责物联网终端设备的连接与管理，优化传输协议。',
    requiredSkills: ['MQTT', 'C++', '嵌入式开发'],
    bonusSkills: ['边缘计算', '5G通信'],
    scenarios: '智能家居、工业4.0',
    status: 'active',
    source: 'BOSS直聘',
    date: '2025-05-22'
  },
  {
    id: 'j4',
    name: '智能系统运维',
    category: '智能系统',
    heat: 75,
    duties: '维护 AI 驱动的自动化系统，监控性能瓶颈。',
    requiredSkills: ['Linux', 'Docker', 'K8s'],
    bonusSkills: ['AIOps', 'Python脚本'],
    scenarios: '云计算、数据中心',
    status: 'pending',
    source: 'AI 挖掘',
    date: '2025-06-01'
  },
  {
    id: 'j5',
    name: '元宇宙场景设计师',
    category: '数字孪生',
    heat: 90,
    duties: '构建 3D 虚拟场景，提升用户沉浸式体验。',
    requiredSkills: ['Unity', 'Unreal Engine', '3D建模'],
    bonusSkills: ['VR/AR', '交互设计'],
    scenarios: '游戏、教育、展览',
    status: 'active',
    source: '行业报告',
    date: '2025-05-25'
  },
  {
    id: 'j6',
    name: '区块链安全专家',
    category: '信息安全',
    heat: 85,
    duties: '审计智能合约代码，防范黑客攻击与数据泄露。',
    requiredSkills: ['Solidity', '智能合约', '密码学'],
    bonusSkills: ['以太坊', 'Go语言'],
    scenarios: 'Web3、金融、供应链',
    status: 'active',
    source: 'GitHub 趋势',
    date: '2025-05-28'
  },
  {
    id: 'j7',
    name: '数字孪生工程师',
    category: '数字孪生',
    heat: 78,
    duties: '通过物理模型和传感器数据，在虚拟空间中完成映射。',
    requiredSkills: ['数字孪生', '仿真模拟', '数据集成'],
    bonusSkills: ['工业互联网', '数字建模'],
    scenarios: '智慧城市、工业制造',
    status: 'active',
    source: '行业报告',
    date: '2025-05-29'
  },
  {
    id: 'j8',
    name: '碳中和技术专家',
    category: '绿色能源',
    heat: 92,
    duties: '规划碳中和实施路径，优化能源消耗结构。',
    requiredSkills: ['碳捕集', '能源管理', '环境工程'],
    bonusSkills: ['ESG', '新能源'],
    scenarios: '能源、环保、咨询',
    status: 'active',
    source: '政策导向',
    date: '2025-05-30'
  },
  {
    id: 'j9',
    name: '隐私计算工程师',
    category: '大数据',
    heat: 84,
    duties: '在保护隐私的前提下实现数据价值的挖掘与共享。',
    requiredSkills: ['联邦学习', '多方安全计算', '同态加密'],
    bonusSkills: ['数据安全', '零知识证明'],
    scenarios: '医疗、金融、政务',
    status: 'pending',
    source: 'AI 挖掘',
    date: '2025-06-02'
  },
  {
    id: 'j10',
    name: '低代码平台架构师',
    category: '智能系统',
    heat: 70,
    duties: '设计高灵活性的低代码开发平台，降低应用开发门槛。',
    requiredSkills: ['可视化引擎', '元数据驱动', '低代码框架'],
    bonusSkills: ['微服务', 'DevOps'],
    scenarios: '企业办公、快速原型',
    status: 'active',
    source: '猎聘',
    date: '2025-05-20'
  }
];

export const mockSkills: Skill[] = [
  { id: 's1', name: 'Python', level: 'intermediate', category: '编程语言' },
  { id: 's2', name: 'NLP', level: 'advanced', category: '人工智能' },
  { id: 's3', name: '提示词工程', level: 'intermediate', category: '人工智能' },
  { id: 's4', name: 'Hadoop', level: 'advanced', category: '大数据' },
  { id: 's5', name: 'Spark', level: 'intermediate', category: '大数据' },
  { id: 's6', name: 'MQTT', level: 'intermediate', category: '物联网' },
  { id: 's7', name: 'C++', level: 'advanced', category: '编程语言' },
  { id: 's8', name: 'Unity', level: 'intermediate', category: '图形学' },
  { id: 's9', name: 'Docker', level: 'intermediate', category: '运维' },
  { id: 's10', name: 'K8s', level: 'advanced', category: '运维' },
  { id: 's11', name: 'Solidity', level: 'intermediate', category: '区块链' },
  { id: 's12', name: '联邦学习', level: 'advanced', category: '人工智能' },
  { id: 's13', name: '碳捕集', level: 'advanced', category: '绿色能源' },
  { id: 's14', name: '数字孪生', level: 'intermediate', category: '数字孪生' },
  { id: 's15', name: 'LLM 微调', level: 'advanced', category: '人工智能' },
  { id: 's16', name: '智能合约', level: 'intermediate', category: '区块链' },
  { id: 's17', name: '密码学', level: 'advanced', category: '信息安全' }
];

export const mockGraphData = {
  nodes: [
    ...mockJobs.map(j => ({ id: j.id, label: j.name, type: 'job' as const, category: j.category })),
    ...mockSkills.map(s => ({ id: s.id, label: s.name, type: 'skill' as const, category: s.category }))
  ],
  links: [
    { source: 'j1', target: 's1' },
    { source: 'j1', target: 's2' },
    { source: 'j1', target: 's3' },
    { source: 'j2', target: 's4' },
    { source: 'j2', target: 's5' },
    { source: 'j3', target: 's6' },
    { source: 'j3', target: 's7' },
    { source: 'j4', target: 's9' },
    { source: 'j4', target: 's10' },
    { source: 'j5', target: 's8' },
    { source: 'j6', target: 's11' },
    { source: 'j6', target: 's16' },
    { source: 'j6', target: 's17' },
    { source: 'j7', target: 's14' },
    { source: 'j8', target: 's13' },
    { source: 'j9', target: 's12' },
    { source: 'j10', target: 's1' },
    { source: 'j1', target: 's15' }
  ]
};

export const mockReports = {
  jobTrends: [
    { month: '1月', count: 45 },
    { month: '2月', count: 52 },
    { month: '3月', count: 61 },
    { month: '4月', count: 58 },
    { month: '5月', count: 72 },
    { month: '6月', count: 85 },
  ],
  marketTrends: [
    { month: '1月', demand: 2400 },
    { month: '2月', demand: 2800 },
    { month: '3月', demand: 3200 },
    { month: '4月', demand: 3000 },
    { month: '5月', demand: 3800 },
    { month: '6月', demand: 4200 },
  ],
  skillGrowth: [
    { name: 'AI', value: 120 },
    { name: '大数据', value: 95 },
    { name: '物联网', value: 70 },
    { name: '数字孪生', value: 50 },
  ],
  jobStatus: [
    { name: '活跃', value: 150 },
    { name: '待审', value: 25 },
    { name: '归档', value: 15 },
  ]
};
