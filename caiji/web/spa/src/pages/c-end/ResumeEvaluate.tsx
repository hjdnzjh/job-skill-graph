import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, CheckCircle2, AlertCircle, ArrowRight, RefreshCw, Star, Info } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { mockJobs } from '../../lib/mockData';
import { ScrollReveal, StaggerContainer, StaggerItem } from '../../components/common/ScrollReveal';
import { CountUp } from '../../components/common/CountUp';

export default function ResumeEvaluate() {
  const [isUploading, setIsUploading] = useState(false);
  const [showResult, setShowResult] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState(mockJobs[0].id);
  const [file, setFile] = useState<File | null>(null);

  const handleUpload = () => {
    if (!file) return;
    setIsUploading(true);
    // Simulate API call
    setTimeout(() => {
      setIsUploading(false);
      setShowResult(true);
    }, 2500);
  };

  const currentJob = mockJobs.find(j => j.id === selectedJobId) || mockJobs[0];

  const skillCloud = [
    { name: 'Python', size: 'text-2xl', color: 'text-blue-400' },
    { name: 'NLP', size: 'text-xl', color: 'text-purple-400' },
    { name: 'Git', size: 'text-sm', color: 'text-slate-400' },
    { name: 'Docker', size: 'text-lg', color: 'text-cyan-400' },
    { name: 'SQL', size: 'text-md', color: 'text-emerald-400' },
    { name: 'React', size: 'text-sm', color: 'text-indigo-400' },
    { name: 'PyTorch', size: 'text-lg', color: 'text-orange-400' },
  ];

  return (
    <div className="container mx-auto px-4 py-12 max-w-5xl">
      <ScrollReveal direction="down" className="text-center mb-12">
        <h1 className="text-4xl font-bold text-white mb-4">简历测评 & 人岗差距诊断</h1>
        <p className="text-slate-400">上传你的简历，我们将通过 AI 算法深度解析你与目标新兴岗位的匹配程度。</p>
      </ScrollReveal>

      <AnimatePresence mode="wait">
        {!showResult ? (
          <motion.div 
            key="upload-view"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.05 }}
            className="space-y-8"
          >
            {/* Upload Area */}
            <ScrollReveal direction="up" delay={0.2}>
              <Card className="relative border-dashed border-2 border-slate-800 bg-slate-900/20 hover:border-indigo-500/50 transition-all group overflow-hidden">
                <CardContent className="p-12 flex flex-col items-center justify-center text-center">
                  {isUploading && (
                    <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
                      <div className="relative">
                        <motion.div 
                          animate={{ rotate: 360 }}
                          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                          className="w-24 h-24 rounded-full border-t-2 border-r-2 border-indigo-500"
                        />
                        <motion.div 
                          animate={{ rotate: -360 }}
                          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                          className="absolute inset-2 rounded-full border-b-2 border-l-2 border-cyan-400"
                        />
                        <div className="absolute inset-0 flex items-center justify-center">
                          <FileText className="h-8 w-8 text-indigo-400 animate-pulse" />
                        </div>
                      </div>
                      <motion.p 
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="mt-6 text-white font-medium"
                      >
                        AI 深度解析中...
                      </motion.p>
                    </div>
                  )}
                  
                  <div className="w-20 h-20 rounded-full bg-slate-800 flex items-center justify-center mb-6 group-hover:bg-indigo-500/20 group-hover:text-indigo-400 transition-colors">
                    <Upload className="h-10 w-10 text-slate-500 group-hover:text-indigo-400" />
                  </div>
                  <h3 className="text-xl font-bold text-white mb-2">拖拽文件至此 或 点击上传</h3>
                  <p className="text-sm text-slate-500 mb-6">支持 PDF, Word 格式 (最大 10MB)</p>
                  <input 
                    type="file" 
                    id="resume-upload" 
                    className="hidden" 
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                  <Button asChild variant="outline" className="border-slate-700 hover:border-indigo-500">
                    <label htmlFor="resume-upload" className="cursor-pointer">选择文件</label>
                  </Button>
                  {file && (
                    <motion.div 
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-4 text-indigo-400 text-sm font-medium flex items-center gap-2"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      已选择: {file.name}
                    </motion.div>
                  )}
                </CardContent>
              </Card>
            </ScrollReveal>

            {/* Job Selection */}
            <ScrollReveal direction="up" delay={0.4} className="max-w-md mx-auto space-y-4">
              <label className="block text-sm font-medium text-slate-300 text-center">选择目标岗位进行对标</label>
              <select 
                value={selectedJobId}
                onChange={(e) => setSelectedJobId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
              >
                {mockJobs.map(job => (
                  <option key={job.id} value={job.id}>{job.name}</option>
                ))}
              </select>
              <Button 
                className="w-full h-12 text-lg bg-indigo-600 hover:bg-indigo-500" 
                disabled={!file || isUploading}
                onClick={handleUpload}
              >
                {isUploading ? (
                  <span className="flex items-center gap-2">
                    <RefreshCw className="h-5 w-5 animate-spin" />
                    分析中...
                  </span>
                ) : '一键开始测评'}
              </Button>
            </ScrollReveal>
          </motion.div>
        ) : (
          <motion.div 
            key="result-view"
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-8"
          >
            {/* Result Header */}
            <Card className="border-slate-800 bg-slate-900/40 backdrop-blur-md overflow-hidden relative">
              <div className="absolute top-0 right-0 p-4">
                <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/20">分析完成</Badge>
              </div>
              <CardContent className="p-8">
                <div className="flex flex-col md:flex-row items-center gap-12">
                  <div className="relative w-48 h-48 flex items-center justify-center">
                    <svg className="w-full h-full -rotate-90">
                      <circle cx="96" cy="96" r="88" fill="none" stroke="#1e293b" strokeWidth="12" />
                      <motion.circle 
                        cx="96" cy="96" r="88" fill="none" stroke="#6366f1" strokeWidth="12" strokeLinecap="round"
                        initial={{ strokeDasharray: "0 553" }}
                        animate={{ strokeDasharray: "470 553" }}
                        transition={{ duration: 2, ease: "easeOut", delay: 0.5 }}
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <div className="text-5xl font-black text-white">
                        <CountUp to={85} />
                      </div>
                      <div className="text-slate-500 text-sm font-bold uppercase tracking-widest">匹配指数</div>
                    </div>
                  </div>
                  
                  <div className="flex-1 space-y-4 text-center md:text-left">
                    <div>
                      <h2 className="text-3xl font-bold text-white mb-1">对标结果: {currentJob.name}</h2>
                      <p className="text-slate-400">你的背景与该岗位高度契合，具备极强的竞争力。</p>
                    </div>
                    <div className="flex flex-wrap gap-3 justify-center md:justify-start">
                      <Badge variant="secondary" className="bg-indigo-500/10 text-indigo-400 border-indigo-500/20">核心能力 92%</Badge>
                      <Badge variant="secondary" className="bg-cyan-500/10 text-cyan-400 border-cyan-500/20">经验匹配 78%</Badge>
                      <Badge variant="secondary" className="bg-purple-500/10 text-purple-400 border-purple-500/20">潜力评估 A+</Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Skill Gap */}
              <Card className="lg:col-span-2 border-slate-800 bg-slate-900/40">
                <CardHeader>
                  <CardTitle className="text-xl flex items-center gap-2">
                    <Star className="h-5 w-5 text-yellow-500" />
                    技能雷达对比
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <StaggerContainer stagger={0.15} className="space-y-6">
                    {['技术深度', '业务理解', '协作沟通', '学习能力', '工具链熟练度'].map((skill, i) => (
                      <StaggerItem key={i} direction="right">
                        <div className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span className="text-slate-300">{skill}</span>
                            <span className="text-indigo-400 font-bold">
                              {i === 1 ? '需要提升' : '优势领域'}
                            </span>
                          </div>
                          <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden relative">
                            <motion.div 
                              initial={{ width: 0 }}
                              animate={{ width: `${80 + Math.random() * 15}%` }}
                              transition={{ duration: 1, delay: 0.8 + i * 0.1 }}
                              className="h-full bg-indigo-500 rounded-full"
                            />
                            {/* Target mark */}
                            <div className="absolute top-0 right-[15%] h-full w-0.5 bg-cyan-400 z-10 shadow-[0_0_5px_#22d3ee]" />
                          </div>
                        </div>
                      </StaggerItem>
                    ))}
                  </StaggerContainer>
                </CardContent>
              </Card>

              {/* Suggestions */}
              <Card className="border-slate-800 bg-slate-900/40">
                <CardHeader>
                  <CardTitle className="text-xl flex items-center gap-2">
                    <AlertCircle className="h-5 w-5 text-indigo-400" />
                    补齐建议
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/10">
                    <h4 className="font-bold text-white mb-2 flex items-center gap-2">
                      <Info className="h-4 w-4 text-indigo-400" />
                      技能短板
                    </h4>
                    <ul className="text-sm text-slate-400 space-y-2">
                      <li className="flex items-start gap-2">
                        <span className="text-indigo-500 font-bold">•</span>
                        缺乏分布式系统设计经验
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-indigo-500 font-bold">•</span>
                        建议补充 Kubernetes 相关实践
                      </li>
                    </ul>
                  </div>
                  <div className="p-4 rounded-xl bg-cyan-500/5 border border-cyan-500/10">
                    <h4 className="font-bold text-white mb-2">推荐学习路径</h4>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-300">云原生架构进阶</span>
                        <Button variant="link" size="sm" className="h-auto p-0 text-indigo-400">查看课程</Button>
                      </div>
                      <div className="h-1 w-full bg-slate-800 rounded-full">
                        <div className="h-full w-1/3 bg-cyan-500 rounded-full" />
                      </div>
                    </div>
                  </div>
                  <Button 
                    variant="outline" 
                    className="w-full border-slate-700 hover:bg-slate-800"
                    onClick={() => setShowResult(false)}
                  >
                    重新测评
                  </Button>
                </CardContent>
              </Card>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
