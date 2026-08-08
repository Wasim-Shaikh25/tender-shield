"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Modal, ModalHeader, ModalBody, ModalFooter } from "@/components/ui/modal";
import { Tabs, TabList, TabTrigger, TabContent } from "@/components/ui/tabs";
import { Dropdown, DropdownItem, DropdownSeparator } from "@/components/ui/dropdown";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Skeleton, SkeletonText, SkeletonCard } from "@/components/ui/skeleton";
import { Tooltip } from "@/components/ui/tooltip";
import { Breadcrumb, BreadcrumbItem } from "@/components/ui/breadcrumb";
import { Toast, useToast } from "@/components/ui/toast";

export default function ComponentsDemo() {
  const [modalOpen, setModalOpen] = useState(false);
  const { toasts, addToast, removeToast, success, error, warning, info } = useToast();

  return (
    <div className="min-h-screen bg-bg-primary p-8">
      <div className="max-w-6xl mx-auto space-y-12">
        {/* Header */}
        <div>
          <h1 className="text-4xl font-bold text-text-primary mb-2">Components Showcase</h1>
          <p className="text-text-secondary">Comprehensive demonstration of all UI components with WCAG AA accessibility</p>
        </div>

        {/* Breadcrumb */}
        <Card>
          <CardHeader>
            <CardTitle>Breadcrumb Navigation</CardTitle>
            <CardDescription>Navigation path component</CardDescription>
          </CardHeader>
          <CardContent>
            <Breadcrumb>
              <BreadcrumbItem href="/">Home</BreadcrumbItem>
              <BreadcrumbItem href="/components-demo">Components</BreadcrumbItem>
              <BreadcrumbItem isActive>Showcase</BreadcrumbItem>
            </Breadcrumb>
          </CardContent>
        </Card>

        {/* Tabs */}
        <Card>
          <CardHeader>
            <CardTitle>Tabs Component</CardTitle>
            <CardDescription>Tab navigation with animated content switching and keyboard support (Arrow keys)</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultTab="overview">
              <TabList>
                <TabTrigger value="overview">Overview</TabTrigger>
                <TabTrigger value="features">Features</TabTrigger>
                <TabTrigger value="usage">Usage</TabTrigger>
              </TabList>
              <TabContent value="overview">
                <p className="text-text-secondary">Tabs provide a way to organize content into separate views that share the same space.</p>
              </TabContent>
              <TabContent value="features">
                <ul className="list-disc list-inside space-y-2 text-text-secondary">
                  <li>Animated content transitions with Framer Motion</li>
                  <li>Keyboard navigation (Arrow Left/Right, Tab)</li>
                  <li>ARIA roles and semantic HTML</li>
                  <li>Focus management and visual indicators</li>
                </ul>
              </TabContent>
              <TabContent value="usage">
                <code className="block bg-bg-secondary p-4 rounded text-sm overflow-auto text-text-primary">
                  {`<Tabs defaultTab="tab1">
  <TabList>
    <TabTrigger value="tab1">Tab 1</TabTrigger>
    <TabTrigger value="tab2">Tab 2</TabTrigger>
  </TabList>
  <TabContent value="tab1">Content 1</TabContent>
  <TabContent value="tab2">Content 2</TabContent>
</Tabs>`}
                </code>
              </TabContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Modal */}
        <Card>
          <CardHeader>
            <CardTitle>Modal Dialog</CardTitle>
            <CardDescription>Modal with focus management, ESC to close, and spring animations</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => setModalOpen(true)} variant="primary">Open Modal</Button>
            <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title="Sample Modal" size="md">
              <ModalBody>
                <p className="text-text-secondary mb-4">
                  This modal demonstrates:
                </p>
                <ul className="list-disc list-inside space-y-2 text-text-secondary">
                  <li>Focus trap - focus stays within modal</li>
                  <li>ESC key closes the modal</li>
                  <li>Backdrop click closes the modal</li>
                  <li>Focus restoration after close</li>
                  <li>Spring animation on open/close</li>
                </ul>
              </ModalBody>
              <ModalFooter>
                <Button onClick={() => setModalOpen(false)} variant="secondary">Close</Button>
                <Button onClick={() => setModalOpen(false)} variant="primary">Confirm</Button>
              </ModalFooter>
            </Modal>
          </CardContent>
        </Card>

        {/* Dropdown */}
        <Card>
          <CardHeader>
            <CardTitle>Dropdown Menu</CardTitle>
            <CardDescription>Menu with click-outside detection, keyboard navigation, and ARIA roles</CardDescription>
          </CardHeader>
          <CardContent>
            <Dropdown trigger={<Button variant="secondary">Actions ▼</Button>} align="left">
              <DropdownItem onClick={() => success("Action 1 completed")}>
                Action 1
              </DropdownItem>
              <DropdownItem onClick={() => info("Action 2 selected")}>
                Action 2
              </DropdownItem>
              <DropdownSeparator />
              <DropdownItem destructive onClick={() => error("Deleted item")}>
                Delete
              </DropdownItem>
            </Dropdown>
          </CardContent>
        </Card>

        {/* Table */}
        <Card>
          <CardHeader>
            <CardTitle>Table Component</CardTitle>
            <CardDescription>Semantic table with proper headers and alignment options</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead align="left">Component</TableHead>
                  <TableHead align="center">Status</TableHead>
                  <TableHead align="right">Score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell>Button</TableCell>
                  <TableCell align="center"><Badge variant="success">Ready</Badge></TableCell>
                  <TableCell align="right">98%</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Modal</TableCell>
                  <TableCell align="center"><Badge variant="success">Ready</Badge></TableCell>
                  <TableCell align="right">100%</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Tabs</TableCell>
                  <TableCell align="center"><Badge variant="success">Ready</Badge></TableCell>
                  <TableCell align="right">100%</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Skeleton */}
        <Card>
          <CardHeader>
            <CardTitle>Skeleton Loading States</CardTitle>
            <CardDescription>Placeholder components for loading states</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm font-medium text-text-secondary mb-2">Text Skeleton:</p>
                <SkeletonText lines={3} />
              </div>
              <div>
                <p className="text-sm font-medium text-text-secondary mb-2">Card Skeleton:</p>
                <SkeletonCard />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Tooltip */}
        <Card>
          <CardHeader>
            <CardTitle>Tooltip Component</CardTitle>
            <CardDescription>Positioned tooltips with delay and arrow indicators</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <Tooltip content="Tooltip at top" position="top">
                <Button variant="secondary">Top</Button>
              </Tooltip>
              <Tooltip content="Tooltip at bottom" position="bottom">
                <Button variant="secondary">Bottom</Button>
              </Tooltip>
              <Tooltip content="Tooltip on left" position="left">
                <Button variant="secondary">Left</Button>
              </Tooltip>
              <Tooltip content="Tooltip on right" position="right">
                <Button variant="secondary">Right</Button>
              </Tooltip>
            </div>
          </CardContent>
        </Card>

        {/* Badges & Status */}
        <Card>
          <CardHeader>
            <CardTitle>Badge & Status Components</CardTitle>
            <CardDescription>Visual status indicators</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex gap-2 flex-wrap">
                <Badge variant="primary">Primary</Badge>
                <Badge variant="secondary">Secondary</Badge>
                <Badge variant="success">Success</Badge>
                <Badge variant="warning">Warning</Badge>
                <Badge variant="error">Error</Badge>
                <Badge variant="info">Info</Badge>
              </div>
              <Alert variant="info">
                Info alert with helpful information
              </Alert>
              <Alert variant="success">
                Success alert confirming an action
              </Alert>
              <Alert variant="warning">
                Warning alert about a potential issue
              </Alert>
              <Alert variant="error">
                Error alert indicating a problem
              </Alert>
            </div>
          </CardContent>
        </Card>

        {/* Toast Notifications */}
        <Card>
          <CardHeader>
            <CardTitle>Toast Notifications</CardTitle>
            <CardDescription>Auto-dismissing notifications with type variants</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 flex-wrap">
              <Button onClick={() => success("Success message!")} variant="secondary" size="sm">
                Success Toast
              </Button>
              <Button onClick={() => error("Error message!")} variant="secondary" size="sm">
                Error Toast
              </Button>
              <Button onClick={() => warning("Warning message!")} variant="secondary" size="sm">
                Warning Toast
              </Button>
              <Button onClick={() => info("Info message!")} variant="secondary" size="sm">
                Info Toast
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Accessibility Features */}
        <Card>
          <CardHeader>
            <CardTitle>Accessibility Features (WCAG 2.1 AA)</CardTitle>
            <CardDescription>All components are built with accessibility in mind</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-text-secondary">
              <div className="flex items-start gap-3">
                <span className="text-success font-bold">✓</span>
                <div>
                  <p className="font-medium text-text-primary">Keyboard Navigation</p>
                  <p className="text-sm">Tab, Enter, Arrow keys, ESC all work across components</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-success font-bold">✓</span>
                <div>
                  <p className="font-medium text-text-primary">Focus Management</p>
                  <p className="text-sm">Modal focus traps, visible focus indicators on all elements</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-success font-bold">✓</span>
                <div>
                  <p className="font-medium text-text-primary">ARIA Semantics</p>
                  <p className="text-sm">Proper roles, labels, and state attributes for screen readers</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="text-success font-bold">✓</span>
                <div>
                  <p className="font-medium text-text-primary">Color Contrast</p>
                  <p className="text-sm">All text meets WCAG AA 4.5:1 contrast ratios</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Toast Container */}
        <div className="fixed bottom-4 right-4 z-50 space-y-2 max-w-sm">
          {toasts.map((toast) => (
            <Toast key={toast.id} {...toast} onClose={removeToast} />
          ))}
        </div>
      </div>
    </div>
  );
}
