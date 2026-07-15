import React, { useState, useMemo } from 'react';
import { ChevronRight, ChevronDown, Search } from 'lucide-react';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';

export interface TaxonomyNode {
  code: string;
  name: string;
  count?: number;
  total_demand?: number;
  children?: TaxonomyNode[];
  groups?: TaxonomyNode[];
  types?: TaxonomyNode[];
  skills?: { name: string; demand: number }[];
  categories?: TaxonomyNode[];
  titles?: { name: string; job_count: number }[];
}

interface TaxonomyTreeProps {
  data: TaxonomyNode[];
  value: string[];
  onChange: (codes: string[]) => void;
  multiple?: boolean;
  searchable?: boolean;
  placeholder?: string;
}

/** Resolve children from a node, regardless of which key the API uses */
function getNodeChildren(node: TaxonomyNode): TaxonomyNode[] {
  if (node.children?.length) return node.children;
  if (node.groups?.length) return node.groups;
  if (node.types?.length) return node.types;
  if (node.categories?.length) return node.categories;
  // Leaf-level items (skills or titles)
  if (node.skills?.length) {
    return node.skills.map((s) => ({
      code: `${node.code}::${s.name}`,
      name: s.name,
      count: s.demand,
    }));
  }
  if (node.titles?.length) {
    return node.titles.map((t: { name: string; job_count: number }) => ({
      code: `${node.code}::${t.name}`,
      name: t.name,
      count: t.job_count,
    }));
  }
  return [];
}

function getNodeCount(node: TaxonomyNode): number {
  if (node.count !== undefined) return node.count;
  if (node.total_demand !== undefined) return node.total_demand;
  const children = getNodeChildren(node);
  if (children.length) return children.reduce((sum, c) => sum + getNodeCount(c), 0);
  return 0;
}

function collectLeafCodes(node: TaxonomyNode): string[] {
  const children = getNodeChildren(node);
  if (!children.length) return [node.code];
  return children.flatMap((c) => collectLeafCodes(c));
}

function matchesSearch(node: TaxonomyNode, term: string): boolean {
  if (!term) return true;
  const lower = term.toLowerCase();
  if (node.name.toLowerCase().includes(lower)) return true;
  if (node.code.toLowerCase().includes(lower)) return true;
  return getNodeChildren(node).some((c) => matchesSearch(c, term));
}

interface TreeNodeRowProps {
  node: TaxonomyNode;
  depth: number;
  selectedCodes: Set<string>;
  onToggle: (code: string) => void;
  searchTerm: string;
  multiple: boolean;
}

function TreeNodeRow({ node, depth, selectedCodes, onToggle, searchTerm, multiple }: TreeNodeRowProps) {
  const children = useMemo(() => getNodeChildren(node), [node]);
  const [expanded, setExpanded] = useState(depth < 1);
  const leafCodes = useMemo(() => collectLeafCodes(node), [node]);
  const allSelected = leafCodes.length > 0 && leafCodes.every((c) => selectedCodes.has(c));
  const someSelected = leafCodes.some((c) => selectedCodes.has(c));
  const count = getNodeCount(node);

  const visible = !searchTerm || matchesSearch(node, searchTerm);
  if (!visible) return null;

  const handleCheck = () => {
    if (multiple) {
      if (allSelected) {
        // Deselect all leaves under this node
        onToggle(node.code); // signal to parent
      } else {
        // Select all leaves under this node
        leafCodes.forEach((c) => {
          if (!selectedCodes.has(c)) onToggle(c);
        });
      }
    } else {
      onToggle(node.code);
    }
  };

  const handleExpand = (e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded(!expanded);
  };

  return (
    <div>
      <div
        className="flex items-center gap-1.5 py-1.5 px-2 rounded-md hover:bg-slate-800/50 cursor-pointer transition-colors group"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={handleCheck}
      >
        {/* Expand/Collapse arrow */}
        {children.length > 0 ? (
          <button
            onClick={handleExpand}
            className="p-0.5 text-slate-500 hover:text-slate-300 flex-shrink-0"
          >
            {expanded ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
        ) : (
          <span className="w-5 flex-shrink-0" />
        )}

        {/* Checkbox */}
        <div
          className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center transition-colors ${
            allSelected
              ? 'bg-indigo-600 border-indigo-600'
              : someSelected
              ? 'bg-indigo-600/50 border-indigo-600'
              : 'border-slate-600 group-hover:border-slate-400'
          }`}
        >
          {(allSelected || someSelected) && (
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>

        {/* Label */}
        <span className="text-sm text-slate-200 group-hover:text-white truncate flex-1">
          {node.name}
        </span>

        {/* Count badge */}
        {count > 0 && (
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 flex-shrink-0">
            {count}
          </Badge>
        )}
      </div>

      {/* Children */}
      {expanded && children.length > 0 && (
        <div>
          {children.map((child) => (
            <TreeNodeRow
              key={child.code}
              node={child}
              depth={depth + 1}
              selectedCodes={selectedCodes}
              onToggle={onToggle}
              searchTerm={searchTerm}
              multiple={multiple}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function TaxonomyTree({
  data,
  value,
  onChange,
  multiple = true,
  searchable = true,
  placeholder = '搜索...',
}: TaxonomyTreeProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const selectedSet = useMemo(() => new Set(value), [value]);

  const handleToggle = (code: string) => {
    if (multiple) {
      if (selectedSet.has(code)) {
        onChange(value.filter((c) => c !== code));
      } else {
        onChange([...value, code]);
      }
    } else {
      onChange(value[0] === code ? [] : [code]);
    }
  };

  return (
    <div className="space-y-2">
      {searchable && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <Input
            placeholder={placeholder}
            className="pl-10 h-9 text-sm"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      )}

      <div className="max-h-80 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950/50 p-2">
        {data.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-4">暂无数据</p>
        ) : (
          data.map((node) => (
            <TreeNodeRow
              key={node.code}
              node={node}
              depth={0}
              selectedCodes={selectedSet}
              onToggle={handleToggle}
              searchTerm={searchTerm}
              multiple={multiple}
            />
          ))
        )}
      </div>
    </div>
  );
}

export default TaxonomyTree;
