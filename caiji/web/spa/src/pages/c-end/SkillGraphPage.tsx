import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Network, Info, Layers, Calendar, ChevronRight, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { SkillGraph } from '../../components/common/SkillGraph';
import { Drawer } from '../../components/common/Drawer';
import { Badge } from '../../components/ui/badge';
import { getGraphExport } from '../../services/api';
import { ScrollReveal } from '../../components/common/ScrollReveal';

export default function SkillGraphPage() {
  const [activeTab, setActiveTab] = useState<'tech' | 'level'>('tech');
  const [selectedYear, setSelectedYear] = useState('2025');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [graphData, setGraphData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getGraphExport(200).then(d => {
      const nodes = d.nodes.map(n => ({ id: String(n.node_id), label: n.name, type: n.label === 'Skill' ? 'skill' : 'job', category: n.category }));
      const links = d.edges.map(e => ({ source: String(d.nodes.find(n => n.name === e.source_name && n.label === e.source_label)?.node_id || ''), target: String(d.nodes.find(n => n.name === e.target_name && n.label === e.target_label)?.node_id || ''), }));
      setGraphData({ nodes: nodes.filter(n => n.id), links: links.filter(e => e.source && e.target) });
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleNodeClick = (node: any) => {
    setSelectedNode(node);
    setIsDrawerOpen(true);
  };

  return loading ? (
    <div className="flex items-center justify-center h-[calc(100vh-64px)]">
      <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
    </div>
  ) : (
    <div className="flex flex-col h-[calc(100vh-64px)] overflow-hidden bg-[#0a0e17]">
      {/* Top Toolbar */}
      <ScrollReveal direction="down" className="flex-shrink-0 border-b border-slate-800 bg-slate-950/50 backdrop-blur-md px-6 py-4 flex items-center justify-between z-10">
        <div className="flex items-center gap-6">
          <div className="flex bg-slate-900 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setActiveTab('tech')}
              className={`relative px-4 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-2 overflow-hidden ${
                activeTab === 'tech' ? 'text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {activeTab === 'tech' && (
                <motion.div 
                  layoutId="tab-bg"
                  className="absolute inset-0 bg-indigo-600 shadow-lg"
                  transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                />
              )}
              <Layers className="h-4 w-4 relative z-10" />
              <span className="relative z-10">技术栈视图</span>
            </button>
            <button
              onClick={() => setActiveTab('level')}
              className={`relative px-4 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-2 overflow-hidden ${
                activeTab === 'level' ? 'text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {activeTab === 'level' && (
                <motion.div 
                  layoutId="tab-bg"
                  className="absolute inset-0 bg-indigo-600 shadow-lg"
                  transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                />
              )}
              <Network className="h-4 w-4 relative z-10" />
              <span className="relative z-10">技能等级视图</span>
            </button>
          </div>

          <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 group hover:border-indigo-500/50 transition-colors">
            <Calendar className="h-4 w-4 text-slate-500 group-hover:text-indigo-400 transition-colors" />
            <select 
              value={selectedYear}
              onChange={(e) => setSelectedYear(e.target.value)}
              className="bg-transparent text-sm text-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="2025">2025 版本</option>
              <option value="2024">2024 版本</option>
              <option value="2023">2023 版本</option>
            </select>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <motion.span 
              animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="w-3 h-3 rounded-full bg-indigo-500"
            />
            岗位节点
          </div>
          <div className="flex items-center gap-2">
            <motion.span 
              animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2, repeat: Infinity, delay: 1 }}
              className="w-3 h-3 rounded-full bg-cyan-500"
            />
            技能节点
          </div>
          <Button variant="ghost" size="sm" className="h-8 gap-1 hover:bg-slate-900">
            <Info className="h-3 w-3" />
            图谱说明
          </Button>
        </div>
      </ScrollReveal>

      {/* Graph Area */}
      <div className="flex-1 relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={selectedYear}
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.02 }}
            transition={{ duration: 0.5 }}
            className="w-full h-full"
          >
            {graphData && <SkillGraph
              data={graphData}
              onNodeClick={handleNodeClick}
              height="100%"
            />}
          </motion.div>
        </AnimatePresence>
        
        {/* Floating Info Overlay */}
        <ScrollReveal direction="right" delay={0.5} className="absolute top-6 left-6 max-w-xs p-4 bg-slate-900/60 border border-slate-800 rounded-xl backdrop-blur-md pointer-events-none">
          <h3 className="text-white font-bold mb-2">当前概览: {selectedYear}</h3>
          <p className="text-xs text-slate-400 leading-relaxed">
            图谱包含 {graphData?.nodes?.filter((n: any) => n.type === 'job').length || 0} 个岗位与 {graphData?.nodes?.filter((n: any) => n.type === 'skill').length || 0} 个技能节点。连线强度代表技能在岗位中的核心程度。
          </p>
          <div className="mt-3 flex items-center gap-2 text-[10px] text-indigo-400">
            <div className="h-1 flex-1 bg-slate-800 rounded-full overflow-hidden">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: "100%" }}
                transition={{ duration: 2, repeat: Infinity }}
                className="h-full bg-indigo-500"
              />
            </div>
            <span>实时同步中</span>
          </div>
        </ScrollReveal>
      </div>

      {/* Node Detail Drawer */}
      <Drawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        title={selectedNode?.label || '节点详情'}
      >
        {selectedNode && (
          <motion.div 
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="space-y-6"
          >
            {selectedNode.type === 'job' ? (
              <>
                <div className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20">
                  <h4 className="text-white font-bold mb-2">岗位节点</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    分类: {selectedNode.category || '未分类'}
                  </p>
                </div>
              </>
            ) : (
              <>
                <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/20">
                  <h4 className="text-white font-bold mb-2">技能节点</h4>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    分类: {selectedNode.category || '未分类'}
                  </p>
                </div>
                <div>
                  <h4 className="text-white font-bold mb-3 flex items-center gap-2">
                    <ChevronRight className="h-4 w-4 text-cyan-400" />
                    关联岗位（图谱实时数据）
                  </h4>
                  <div className="space-y-2">
                    {graphData?.links
                      .filter((l: any) => l.source === selectedNode.id || l.target === selectedNode.id)
                      .slice(0, 8)
                      .map((l: any, i: number) => {
                        const other = graphData.nodes.find((n: any) => n.id === (l.source === selectedNode.id ? l.target : l.source));
                        return other ? (
                          <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 border border-slate-800">
                            <span className="text-sm text-slate-300">{other.label}</span>
                            <Badge className="bg-indigo-500/20 text-indigo-400 border-none text-[10px]">{other.type}</Badge>
                          </div>
                        ) : null;
                      })}
                  </div>
                </div>
              </>
            )}
            <Button className="w-full bg-indigo-600 hover:bg-indigo-500">查看详细对标报告</Button>
          </motion.div>
        )}
      </Drawer>
    </div>
  );
}
