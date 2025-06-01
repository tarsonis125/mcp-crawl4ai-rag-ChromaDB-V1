import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BookOpen, HardDrive, Settings } from 'lucide-react';
/**
 * Interface for navigation items
 */
export interface NavigationItem {
  path: string;
  icon: React.ReactNode;
  label: string;
}
/**
 * Props for the SideNavigation component
 */
interface SideNavigationProps {
  className?: string;
  'data-id'?: string;
}
/**
 * Tooltip component for navigation items
 */
const NavTooltip: React.FC<{
  show: boolean;
  label: string;
  position?: 'left' | 'right';
}> = ({
  show,
  label,
  position = 'right'
}) => {
  if (!show) return null;
  return <div className={`absolute ${position === 'right' ? 'left-full ml-2' : 'right-full mr-2'} top-1/2 -translate-y-1/2 px-2 py-1 rounded bg-black/80 text-white text-xs whitespace-nowrap z-50`} style={{
    pointerEvents: 'none'
  }}>
      {label}
      <div className={`absolute top-1/2 -translate-y-1/2 ${position === 'right' ? 'left-0 -translate-x-full' : 'right-0 translate-x-full'} border-4 ${position === 'right' ? 'border-r-black/80 border-transparent' : 'border-l-black/80 border-transparent'}`}></div>
    </div>;
};
/**
 * SideNavigation - A vertical navigation component
 *
 * This component renders a navigation sidebar with icons and the application logo.
 * It highlights the active route and provides hover effects.
 */
export const SideNavigation: React.FC<SideNavigationProps> = ({
  className = '',
  'data-id': dataId
}) => {
  // State to track which tooltip is currently visible
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null);
  // Default navigation items
  const navigationItems: NavigationItem[] = [{
    path: '/',
    icon: <BookOpen className="h-5 w-5" />,
    label: 'Knowledge Base'
  }, {
    path: '/mcp',
    icon: <HardDrive className="h-5 w-5" />,
    label: 'MCP Server'
  }, {
    path: '/settings',
    icon: <Settings className="h-5 w-5" />,
    label: 'Settings'
  }];
  // Logo configuration
  const logoSrc = "/logo-neon.svg";
  const logoAlt = 'Knowledge Base Logo';
  // Get current location to determine active route
  const location = useLocation();
  return <div data-id={dataId} className={`flex flex-col items-center gap-6 py-6 px-3 rounded-xl backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border border-gray-200 dark:border-zinc-800/50 shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)] ${className}`}>
      {/* Logo */}
      <div className="logo-container p-2 relative">
        <img src={logoSrc} alt={logoAlt} className="w-8 h-8" />
        <NavTooltip show={activeTooltip === 'logo'} label="Knowledge Assistant" />
      </div>
      {/* Navigation links */}
      <nav className="flex flex-col gap-4">
        {navigationItems.map(item => {
        const isActive = location.pathname === item.path;
        return <Link key={item.path} to={item.path} className={`
                relative p-3 rounded-lg flex items-center justify-center
                transition-all duration-300
                ${isActive ? 'bg-gradient-to-b from-white/20 to-white/5 dark:from-white/10 dark:to-black/20 text-blue-600 dark:text-blue-400 shadow-[0_5px_15px_-5px_rgba(59,130,246,0.3)] dark:shadow-[0_5px_15px_-5px_rgba(59,130,246,0.5)]' : 'text-gray-500 dark:text-zinc-500 hover:text-blue-600 dark:hover:text-blue-400'}
              `} onMouseEnter={() => setActiveTooltip(item.path)} onMouseLeave={() => setActiveTooltip(null)} aria-label={item.label}>
              {/* Active state decorations - Modified to place neon line below button with adjusted width */}
              {isActive && <>
                  <span className="absolute inset-0 rounded-lg border border-blue-300 dark:border-blue-500/30"></span>
                  {/* Neon line positioned below the button with reduced width to respect curved edges */}
                  <span className="absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[2px] bg-blue-500 shadow-[0_0_10px_2px_rgba(59,130,246,0.4)] dark:shadow-[0_0_20px_5px_rgba(59,130,246,0.7)]"></span>
                </>}
              {item.icon}
              {/* Custom tooltip */}
              <NavTooltip show={activeTooltip === item.path} label={item.label} />
            </Link>;
      })}
      </nav>
    </div>;
};