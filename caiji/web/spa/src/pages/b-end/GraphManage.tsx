import React, { useState } from 'react';
import { 
  Network, 
  Plus, 
  Trash2, 
  Save, 
  RefreshCw, 
  MousePointer2, 
  Link2,
  Settings,
  Info
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { SkillGraph } from '../../components/common/SkillGraph';
import { Drawer } from '../../components/common/Drawer';
import { mockGraphData, GraphNode } from '../../lib/mockData';
import { Badge } from '../../components/ui/badge';

export default function GraphManage() {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [editMode, setEditMode] = useState<'select' | 'link'>('select');

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
    setIsDrawerOpen(true);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-160px)] overflow-hidden">
      {/* Admin Toolbar */}
      <div className="flex-shrink-0 border-b border-slate-800 bg-slate-950/50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex bg-slate-900 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setEditMode('select')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-2 ${
                editMode === 'select' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <MousePointer2 className="h-3.5 w-3.5" />
              选择模式
            </button>
            <button
              onClick={() => setEditMode('link')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-2 ${
                editMode === 'link' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Link2 className="h-3.5 w-3.5" />
              连线模式
            </button>
          </div>

          <div className="h-6 w-px bg-slate-800 mx-2"></div>

          <Button variant="outline" size="sm" className="h-9 border-slate-700">
            <Plus className="h-4 w-4 mr-2" /> 新增节点
          </Button>
          <Button variant="outline" size="sm" className="h-9 border-slate-700 text-red-400 hover:bg-red-400/10 hover:border-red-400/20" disabled={!selectedNode}>
            <Trash2 className="h-4 w-4 mr-2" /> 删除选中
          </Button>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" className="text-slate-400">
            <RefreshCw className="h-4 w-4 mr-2" /> 重置布局
          </Button>
          <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 shadow-[0_0_15px_rgba(16,185,129,0.2)]">
            <Save className="h-4 w-4 mr-2" /> 保存变更
          </Button>
        </div>
      </div>

      {/* Editor Canvas Area */}
      <div className="flex-1 relative">
        <SkillGraph 
          data={mockGraphData} 
          onNodeClick={handleNodeClick}
          height="100%"
          editable={true}
        />
        
        {/* Helper Tooltip */}
        <div className="absolute top-6 right-6 flex items-center gap-2 text-xs text-slate-500 bg-slate-900/80 p-2 rounded-lg border border-slate-800 backdrop-blur-sm">
          <Info className="h-3.5 w-3.5" />
          {editMode === 'select' ? '点击节点查看属性' : '点击两个节点建立关联'}
        </div>
      </div>

      {/* Admin Node Drawer */}
      <Drawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        title="节点属性编辑"
      >
        {selectedNode && (
          <div className="space-y-6">
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-500 uppercase">节点名称</label>
              <input 
                type="text" 
                defaultValue={selectedNode.label}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-500 uppercase">节点类型</label>
              <div className="flex gap-2">
                <Badge variant={selectedNode.type === 'job' ? 'default' : 'outline'} className="cursor-pointer">岗位</Badge>
                <Badge variant={selectedNode.type === 'skill' ? 'cyan' : 'outline'} className="cursor-pointer">技能</Badge>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-500 uppercase">所属领域/分类</label>
              <select className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                <option>{selectedNode.category || '未分类'}</option>
                <option>AI</option>
                <option>大数据</option>
                <option>物联网</option>
              </select>
            </div>

            <div className="space-y-4 pt-4 border-t border-slate-800">
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                <Settings className="h-4 w-4 text-slate-500" /> 高级配置
              </h4>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">显示权重</span>
                  <input type="range" className="w-32 accent-indigo-500" />
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">发光效果</span>
                  <input type="checkbox" defaultChecked className="w-4 h-4 rounded bg-slate-900 border-slate-800 text-indigo-600" />
                </div>
              </div>
            </div>

            <div className="pt-8 flex gap-3">
              <Button variant="outline" className="flex-1 border-slate-700" onClick={() => setIsDrawerOpen(false)}>取消</Button>
              <Button className="flex-1">更新属性</Button>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
